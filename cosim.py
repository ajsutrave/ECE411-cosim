#!/usr/bin/python
from subprocess import Popen, PIPE, STDOUT
import time
import re
import sys

DEBUG = 1

class colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARNING = '\033[96m'
    FAIL = '\033[91m'
    NORMAL = '\033[0m'

class PCMismatch(Exception):
    pass

class RegMismatch(Exception):
    pass

class Proc:
    proc_regs = [0, 0, 0, 0, 0, 0, 0, 0]
    proc_pc = 0
    halted = False

class BehavioralModel(Proc):

    def __init__(self, asm_file):
        self.__asm_file = asm_file
        #start = time.time()
        self.prev_pc = None
        self.inst_num = 0
        self.reg_pattern = re.compile('r(\d):\t4x([\dA-F]{4})')
        self.pc_pattern = re.compile('pc:\t4x([\dA-F]{4})')
        self.TIMEOUT = 10
        self.asm_pattern = re.compile("->(.+)\n")
        self.line = ''
        self.prev_line = ''

    def advance(self):
        if not self.halted:
            p = Popen( ['./LC3bSimulator', self. __asm_file ], 
                       stdout=PIPE, 
                       stdin=PIPE, 
                       stderr=STDOUT)

            # if time.time() - start > TIMEOUT:
            #     p.communicate(input = 'quit')
            #     print "Timeout..."
            #     break

            p.stdin.write('WR RegFile.R6 0000\n')
            # for i in range(self.inst_num):
            #     p.stdin.write('GOI 1\n' )
            p.stdin.write('CHECKOFF\n')
            p.stdin.write('GOI %d\n' % self.inst_num)            
            p.stdin.write('DRS RegFile\n')
            p.stdin.write('DRS Control\n')
            p.stdin.write('QUIT\n')
            output = p.stdout.read()
            regs = re.findall( self.reg_pattern,  output)
            pc = int(re.findall( self.pc_pattern, output )[0], 16)

            print self.prev_line + colors.NORMAL
            self.prev_line = self.line
            self.line = re.findall( self.asm_pattern, output )[-1]

            #print pc, self.prev_pc, pc == self.prev_pc, self.inst_num, self.line
            if pc == self.prev_pc:
                self.halted = True

            for reg_num, reg_val in regs:
                self.proc_regs[ int(reg_num) ] = reg_val
            self.proc_pc = pc

            self.prev_pc = pc
            self.inst_num += 1
        else:
            raise Exception("Trying to advance a halted proc")
            #print "Trying to advance a halted proc"

class HDLModel(Proc):
    
    def __init__(self, list_file):
        self.__fp = open(list_file)
        [self.__fp.readline() for i in range(4)] # Get rid of headers
        self.reg_pattern = re.compile('\{([\dA-F]{4}).([\dA-F]{4}).([\dA-F]{4}).([\dA-F]{4}).([\dA-F]{4}).([\dA-F]{4}).([\dA-F]{4}).([\dA-F]{4})}')
        self.time_pattern = re.compile('(\d+)\s+\+\d')
        self.pc_pattern = re.compile('[\}\s+]([\dA-F]{4})[\s+\{]')

    def advance(self):
        self.line = self.__fp.readline()
        if self.halted:
            raise Exception("Trying to advance a halted proc")
            #print "Trying to advance a halted proc"
        
        if self.line == '':
            self.halted =  True
            return

        self.time = re.findall( self.time_pattern, self.line )
        self.proc_regs = re.findall( self.reg_pattern, self.line)[0][::-1]
        self.proc_pc = int(re.findall( self.pc_pattern, self.line )[-1], 16)

    
def compare_state(proc1, proc2):
    compare_PC(proc1, proc2)
    compare_reg(proc1, proc2)

def compare_PC(proc1, proc2):
    if abs(proc1.proc_pc - proc2.proc_pc) > 2:
        raise PCMismatch

def compare_reg(proc1, proc2):
    for proc1_reg, proc2_reg in zip(proc1.proc_regs, proc2.proc_regs):
        if proc1_reg != proc2_reg:
            raise RegMismatch

hm = HDLModel(sys.argv[2])
bm = BehavioralModel(sys.argv[1])
start_line = ''
err_color = 0

def print_error_info():
    if err_color == 1:
        print_color = colors.FAIL
    else:
        print_color = colors.GREEN

    print colors.HEADER + str(bm.inst_num) + bm.prev_line, "\t@time " + str(hm.time) + colors.NORMAL
    print colors.BLUE + "     PC   (  R0  ,   R1  ,   R2  ,   R3  ,   R4  ,   R5  ,   R6  ,   R7  )" + colors.NORMAL
    print print_color + str(("HDL: %04X" % hm.proc_pc, hm.proc_regs)) + colors.NORMAL
    print print_color + str(("Sim: %04X" % bm.proc_pc, bm.proc_regs)) + colors.NORMAL
    print colors.BLUE + "**********" + colors.NORMAL


bm.advance()
prev_bm_pc = bm.proc_pc
while not bm.halted and not hm.halted:
    hm.advance()
    start_line = bm.prev_line

    try:
        while hm.proc_pc != bm.proc_pc:
            bm.advance()

        if not bm.halted and not hm.halted:
            if DEBUG:
                print_error_info()
            compare_state(bm, hm)

    except RegMismatch:
        print colors.WARNING + "Reg Mismatch at time " + str(hm.time) + colors.NORMAL
        print_error_info()
        print colors.BLUE + "Error probably between: " + colors.NORMAL
        print colors.WARNING + start_line.strip() + colors.NORMAL
        print colors.WARNING + bm.prev_line.strip() + colors.NORMAL
        sys.exit(1)
        
    except PCMismatch:
        print "PC Mismatch at time " + str(hm.time) + colors.NORMAL
        print_error_info()
        print "Error probably between: " + colors.NORMAL
        print start_line.strip() + colors.NORMAL
        print bm.prev_line.strip() + colors.NORMAL
        sys.exit(2)

print colors.BLUE + "Cosim Passed" + colors.NORMAL
