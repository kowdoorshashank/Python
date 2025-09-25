#TOP MODULE
TOPLEVEL = python_top

#TOP -level Language
TOPLEVEL_LANG = verilog

#Source
VERILOG_SOURCES =$(PWD)/pkg.sv $(PWD)/chi_home_node.sv $(PWD)/chi_requester_node.sv $(PWD)/python_top.sv

#PYTHON test module
MODULE = test_AMBA_CHI

#Simulator
SIM = vcs

#Run command
EXTRA_ARGS += -full64 -sverilog -debug_access+all +vpi -timescale=1ns/1ps

#include cocotb simulator Makefile
include $(shell cocotb-config --makefiles)/simulators/Makefile.$(SIM)
