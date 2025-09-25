import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer
import random
import logging
import os
import time
from enum import IntEnum

# AMBA CHI Opcodes

class Opcode(IntEnum):
    ReadShared = 0
    WriteBack = 1
    WriteUnique = 2

# Logging setup

today = time.strftime("%Y-%m-%d")
log_dir = os.path.join("LOGS", today)
os.makedirs(log_dir, exist_ok=True)

timestamp = time.strftime("%H%M%S")
log_file = os.path.join(log_dir, f"amba_chi_{timestamp}.log")

logger = logging.getLogger("cocotb")
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(log_file, mode="w")
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Transaction modes

class Mode(IntEnum):
    WRITE = 0
    READ = 1
    BACK = 2

# Monitor Home Node

async def monitor_home_response(dut, txn_id, expected_data=None, max_cycles=200):
    """Wait for a response from the Home Node for a given txn_id"""
    for cycle in range(max_cycles):
        await RisingEdge(dut.clk)
        if dut.hn_to_rn_valid.value and int(dut.hn_to_rn_flit.txn_id.value) == txn_id:
            data = int(dut.hn_to_rn_flit.data.value)
            dut._log.info(
                f"Home Node Response: "
                f"txn_id={txn_id}, addr=0x{int(dut.hn_to_rn_flit.address.value):X}, "
                f"data=0x{int(dut.hn_to_rn_flit.data.value):X}, opcode={int(dut.hn_to_rn_flit.opcode.value)}"
            )
            if expected_data is not None and data != expected_data:
                dut._log.warning(f"Data mismatch! Expected 0x{expected_data:X}, got 0x{data:X}")
            return True
    return False

# Main cocotb test

@cocotb.test()
async def amba_chi_sequence_test(dut):
    
    # Start clock
    
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    dut._log.info("CLOCK STARTED")
    
    # Apply reset
    
    dut.rst.value = 0
    dut._log.info("RESET APPLIED")
    await Timer(30, units="ns")
    dut.rst.value = 1
    dut._log.info("RESET RELEASED")
    await RisingEdge(dut.clk)
    
    # Drive ready signals for handshake
    
    dut.rn_to_hn_ready.value = 1
    dut.hn_to_rn_ready.value = 1

    NUM_TRANSACTIONS = 10
    TB_VALID_CYCLES = 3
    mode = Mode.WRITE
    last_write_addr = 0
    last_write_data = 0
    has_write = False
    
    # Simple Home Node memory model
    
    home_memory = {}

    for txn_num in range(NUM_TRANSACTIONS):
        txn_id = random.randint(0, 255)
        addr = random.randint(0, 1023) * 4
        data = random.randint(0, 0xFFFFFFFF)
        opcode = Opcode.WriteUnique
        
        # Mode-specific behavior
        
        if mode == Mode.WRITE:
            opcode = Opcode.WriteUnique
            last_write_addr = addr
            last_write_data = data
            has_write = True
            await RisingEdge(dut.clk)
            await RisingEdge(dut.clk)
            await RisingEdge(dut.clk)
            await RisingEdge(dut.clk)
            await RisingEdge(dut.clk)
            mode = random.choice([Mode.READ, Mode.BACK, Mode.WRITE])

        elif mode == Mode.READ and has_write:
            opcode = Opcode.ReadShared
            addr = last_write_addr
            data = last_write_data
            await RisingEdge(dut.clk)
            await RisingEdge(dut.clk)
            await RisingEdge(dut.clk)
            await RisingEdge(dut.clk)
            await RisingEdge(dut.clk)
            mode = random.choice([Mode.WRITE, Mode.BACK, Mode.READ])

        elif mode == Mode.BACK and has_write:
            opcode = Opcode.WriteBack
            addr = last_write_addr
            data = last_write_data
            await RisingEdge(dut.clk)
            await RisingEdge(dut.clk)
            await RisingEdge(dut.clk)
            await RisingEdge(dut.clk)
            await RisingEdge(dut.clk)
            mode = random.choice([Mode.WRITE, Mode.READ, Mode.BACK])

        dut._log.info(
            f" Sending txn_id={txn_id}, addr=0x{addr:X}, data=0x{data:X}, opcode={opcode.name}"
        )

        # Drive request flit
        
        dut.tb_flit.address.value = addr
        dut.tb_flit.data.value = data
        dut.tb_flit.opcode.value = opcode
        dut.tb_flit.txn_id.value = txn_id
        dut.tb_flit.src_id.value = 1
        dut.tb_flit.tgt_id.value = 0
        dut.tb_flit.flit_type.value = 0  # FLIT_REQ
        dut.tb_valid.value = 1
  
        # Hold tb_valid until tb_ready is high
        
        cycles_waited = 0
        while not dut.tb_ready.value and cycles_waited < 10:
            await RisingEdge(dut.clk)
            cycles_waited += 1

        for _ in range(TB_VALID_CYCLES):
            await RisingEdge(dut.clk)
        dut.tb_valid.value = 0
        dut._log.info(f" Flit sent, waiting for Home Node response...")

        # Update memory model
        
        expected_data = None
        if opcode in [Opcode.WriteUnique, Opcode.WriteBack]:
            home_memory[addr] = data
            expected_data = data
        elif opcode == Opcode.ReadShared:
            expected_data = home_memory.get(addr, 0)
      
        # Monitor Home Node response
        
        got_response = await monitor_home_response(dut, txn_id, expected_data)
        assert got_response, f"[Txn {txn_num}] No response received from Home Node!"

    dut._log.info("All transactions completed successfully!")
