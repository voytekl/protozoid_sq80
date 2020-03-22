#!/usr/bin/python3

# extract_sq80.py
# 
# Copyright (C) 2020 Voytek Lapinski voytekl@octobit.com.au
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
# 

"""

Extract banks/programs from Ensoniq SQ80 disk dump files generated from the
sq80toolkit.

The tool runs in three different modes:

prog        - dump individually saved programs
bank        - dump program banks
virtbank    - dump individual programs consolidated into "virtual banks"

The data is dumped in either pure binary format, or in SYSEX format suitable
for sending directly to the synthesizer over MIDI.

The tool can also be used to generate listings of banks/programs on a disk.

Run with the --help option for usage information.

Thanks and acknowledgements to Rainer Buchty (www.buchty.net) for the
sq80toolkit, and his invaluable work on the SQ80 in general. I have referred to
the source and documentation of the sq80toolkit extensively for the structure
of the disk images.


"""

#--------------------
# imports
#--------------------

import argparse
import re

#--------------------
# globals
#--------------------

FILE_TYPES=['---','SYS','BNK','SNG','SEQ','SYX','PRG']
INIT_PROG=bytes([0x20, 0x20, 0x20, 0x20, 0x20, 0x20, 0x7e, 0x7e, 0x7e, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x7e, 0x7e, 0x7e, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x7e, 0x7e, 0x7e, 0x0, 0x0, 0x0, 0x0, 0x2, 0x0, 0x0, 0x7e, 0x7e, 0x7e, 0x0, 0x0, 0x0, 0x0, 0x2, 0x0, 0x0, 0x16, 0xff, 0xff, 0x80, 0x16, 0xff, 0xff, 0x80, 0x16, 0xff, 0xff, 0x80, 0x24, 0x0, 0xff, 0x0, 0x0, 0x0, 0x68, 0xff, 0x7e, 0x0, 0x24, 0x0, 0xff, 0x0, 0x0, 0x0, 0x68, 0xff, 0x7e, 0x0, 0x24, 0x0, 0xff, 0x0, 0x0, 0x0, 0x68, 0xff, 0x7e, 0x0, 0x7e, 0x7f, 0x0, 0xff, 0x0, 0x0, 0x0, 0x0, 0x3c, 0x71, 0x27, 0x27, 0x8f, 0x0])   

#--------------------
# classes
#--------------------

class directory:
    """ 
    object representation of the disk directory 
    """
    def __init__(self,buf):  
        """ buf is a bytearray containing the disk directory data """
        assert(len(buf)==2048)
        self.buf=buf
    
    def banks(self):
        """ return the bank entries in the directory as a list of bank file_names. None for not defined """
        
        banks=[]
        for i in range(0,40):
            dir_entry=self.buf[(i+10)*13:(i+10+1)*13]
            (file_type,file_name,file_size)=(FILE_TYPES[dir_entry[0]],sqbytes_to_ascii(dir_entry[1:11]),int.from_bytes(dir_entry[11:13],'big'))
            # file_size is not used

            if file_type=='---':
                banks.append(None)
            else:
                assert file_type == 'BNK'
                banks.append(file_name)

        return banks
    
    def progs(self):
        """ return the prog entries in the directory of prog names. None for not defined """

        progs=[]

        for i in range (0,128):
            prog_name_raw=self.buf[650+i*6:650+(i+1)*6]
            if prog_name_raw[0]==0: # if you skip this check, you can recover
                                  # deleted programs. only the first char is
                                  # changed in the directory
                progs.append(None)
            else:
                progs.append(prog_name_raw)
        
        return progs


#--------------------
# functions
#--------------------

def chs_to_offset(c,h,s):
    """
    convert cylinder, head, sector numbers to a byte offset into a disk dump file
    """


    assert(c>=0 and c<80)
    assert(h>=0 and h<2)
    assert(s>=0 and h<6)

    offset = 10 # file header
    offset += (c*2+h)*(5*1024+512)
    offset += s*1024

    #print("c:{},h:{},s:{} = {}".format(c,h,s,offset))

    return offset

def prog_to_chs(prog):
    """
    convert individual program number (counting from 0) to a c,h,s address.
    
    algorithm taken from sq80toolkit.dvi.  One of the overridden sector
    locations was fixed, and two were added (as indicated). The proper values were
    determined by manual inspection of an actual disk image. Without these fixes,
    bad data was being read back for those 3 individual program locations.

    """
    prog=prog
    sw=(prog & 64)|((prog & 63)+2)
    #print ("prog_to_chs: prog={}, sw={}".format(prog,sw))

    if sw == 0x06:
        c = 0x42
        h = 0 
    elif sw == 0x19:
        c = 0x42
        h = 1
    elif sw == 0x1f: 
        c = 0x43
        h = 0   # sq80toolkit has this as 1
    elif sw == 0x26: # sq80toolit doesn't include this case
        c = 0x43
        h = 1
    elif sw == 0x39:
        c = 0x44
        h = 0
    elif sw == 0x3f:
        c = 0x44
        h = 1
    elif sw == 0x4c: # sq80toolkit doesn't include this case
        c = 0x45
        h = 0
    elif sw == 0x53:
        c = 0x45
        h = 1
    elif sw == 0x6c:
        c = 0x46
        h = 0
    elif sw == 0x73:
        c = 0x46
        h = 1
    else: 
        c = (prog & 63)+2
        h = (prog & 64)>>6
    s = 5
    #print("c,h,s:{}.{}.{}".format(c,h,s))
    return(c,h,s)


def sqbytes_to_ascii(b):
    """
    convert Ensoniq charset to ASCII

    The mapping is taken verbatim from sq80toolkit sq80dir.c.
    """

    s=""
    maps={          
        0x00:0x2d,
        0x21:0x30,
        0x23:0x31,
        0x25:0x32,
        0x28:0x33,
        0x29:0x34,
        0x3a:0x35,
        0x3b:0x36,
        0x5b:0x37,
        0x5c:0x38,
        0x5d:0x39
    }

    for c in b:

        if c in maps:
            c=maps[c]

        s+=str(chr(c))

    return s

def read_bank(bank):
    """
    read bank from the image file and return as binary
    """
    assert(bank>=0 and bank<40)

    sector_offset = (bank%20)*4
    c = 64+int(sector_offset/5)
    h = int(bank/20)
    s = sector_offset%5

    data_in=bytearray()

    for i in range(0,4):
        args.imagefile.seek(chs_to_offset(c,h,s));

        if i!=3:
            data_in+=args.imagefile.read(1024)
        else:
            data_in+=args.imagefile.read(1008)

        if s==4:
            s=0
            c+=1
        else:
            s+=1

    return data_in

def dump_bank(bank_data,dump_file): 
    """
    dump the bank binary data in bank_data to dump_file
    """

    if args.dump=='syx':

        data_out=bytearray(b'\xf0\x0f\x02\x00') # SQ80 SYS EX HEADER / CH0
        data_out+=b'\x02' # all program dump

        for b in bank_data:
            data_out+=bytes([b&0x0f, b>>4])

        data_out+=b'\xf7' # end of exclusive

    else:
        data_out=bank_data

    with open(dump_file,"bx") as outfile:
        outfile.write(data_out)

def read_prog(prog_num):
    """
    read in individual program and return as binary
    """
    assert(prog_num >= 0 and prog_num < 128)
    (c,h,s)=prog_to_chs(prog_num)
    
    args.imagefile.seek(chs_to_offset(c,h,s))

    program_data=args.imagefile.read(102) 

    if (directory.progs()[prog_num] != program_data[0:6]):
        raise RuntimeError("program name on disk ({}) doesn't match directory entry ({})".format(program_data[0:6],directory.progs()[prog_num]))
    return program_data

def dump_prog(prog_data,dump_file):
    """
    dump the program binary data in prog_data to dump_file
    """

    if args.dump=='syx':
        data_out=bytearray(b'\xf0\x0f\x02\x00') # SQ80 SYS EX HEADER / CH0
        data_out+=b'\x01' # single program dump

        for b in prog_data:
            data_out+=bytes([b&0x0f, b>>4])

        data_out+=b'\xf7' # end of exclusive

    else:
        data_out=prog_data

    with open(dump_file,"bx") as outfile:
        outfile.write(data_out)

def mode_prog():
    """
    Single program mode
    """

    if (args.dump):
        print("Dumping individual program/s...")
    else:
        print("Listing individual program/s...")

    if args.number:
        assert(args.number>0 and args.number<=128)

    # in list mode (if not dumping and no number selected), progs are output 5
    # to a line (like for virtbanks) to allow for more concise listings of
    # disks to be generated

    printed_flag=False
    for (prog_num,prog_name_raw) in enumerate(directory.progs()):
        if args.list and not args.number and not args.dump and not (prog_num)% 5 and printed_flag:
            printed_flag=False
            print('')

        if args.number and prog_num != args.number - 1: # internally, prog numbers count from 0
            continue

        if prog_name_raw is None:
            if (args.number):
                raise RuntimeError("Specified prog number appears to be blank")
            continue; 

        prog_name=sqbytes_to_ascii(prog_name_raw)

        dump_file="{}{:03}_{}".format(args.prefix or "PROG",prog_num+1,re.sub(r' *$','',prog_name))

        if args.dump=='syx':
            dump_file+='.syx'
        else:
            dump_file+='.bin'

        if args.dump:
            print("  PROG {:2} - {} -> {}".format(prog_num+1,prog_name,dump_file))

            prog_data=read_prog(prog_num)
            dump_prog(prog_data,dump_file)
        else:
            if args.number or not args.list: 
                print("  PROG {:2} - {}".format(prog_num+1,prog_name))
            else:
                printed_flag=True
                print(" {:03}:{: <8}".format(prog_num+1,prog_name),end="")

    if args.list and not args.number and not args.dump and printed_flag:
        print('')

    return
         

def mode_bank():
    """
    Bank mode 
    """

    if (args.dump):
        print("Dumping bank/s...")
    else:
        print("Listing bank/s...")

    # iterate over banks and list/dump them

    if args.number:
        assert(args.number>0 and args.number<=40)

    for (bank_num,bank) in enumerate(directory.banks()): 
        if args.number and bank_num != args.number - 1: # internally, bank numbers count from 0
            continue
        
        if bank is None:
            if (args.number) :
                raise RuntimeError("Specified bank number doesn't exist")
            continue

        dump_file="{}{:02}_{}".format(args.prefix or "BANK",bank_num+1,re.sub(r'\.*$','',bank))
        if args.dump=='syx':
            dump_file+='.syx'
        else:
            dump_file+='.bin'

        if args.dump:
            print("  BANK {:2} - {}   -> {}".format(bank_num+1,bank,dump_file))
            dump_bank(read_bank(bank_num),dump_file)
        elif args.list:
            print("BANK {:2} - {}".format(bank_num+1,bank))
            bank_data=read_bank(bank_num)
            for prog_num in (range(0,40)):
                if prog_num and not prog_num % 5:
                    print('')
                prog_name=sqbytes_to_ascii(bank_data[prog_num*102:prog_num*102+6])
                print(" {:03}:{: <8}".format(prog_num+1,prog_name),end="")
            print('')
        else:
            print("  BANK {:2} - {}".format(bank_num+1,bank))

    return

def mode_virtbank():
    """
    virtual bank mode
    """

    print("Listing virtual bank contents...")

    bank_num=0
    bank_prog_num=0
    bank_data=b''
    banks=[]

    for (prog_num,prog_name_raw) in enumerate(directory.progs()):

        if prog_name_raw is None:
            continue

        bank_name="VIRTBANK{:02}".format(bank_num+1)

        showing_flag = not args.number or args.number-1 == bank_num

        if showing_flag:
            if not bank_prog_num:
                print(bank_name)

            prog_name=sqbytes_to_ascii(prog_name_raw)
            print(" {:03}:{: <8}".format(prog_num+1,prog_name),end="")

        bank_data += read_prog(prog_num)

        bank_prog_num = (bank_prog_num + 1) % 40
        
        if not bank_prog_num:
            banks.append((bank_num,bank_name,bank_data))
            bank_num+=1
            bank_data=b''
        if showing_flag and not bank_prog_num % 5:
            print('')

    if bank_prog_num: # pad out incomplete banks with the init patch
        bank_data += INIT_PROG * (40-bank_prog_num)
        banks.append((bank_num,bank_name,bank_data))

    if args.number and args.number-1 > bank_num:
        print(bank_num)
        raise RuntimeError("No such virtual bank")

    print()
    if (args.dump):
        print("Dumping virtual bank/s...")

        for (bank_num,bank_name,bank_data) in banks:
            if args.number and args.number-1 != bank_num:
                continue
            dump_file="{}{:02}".format(args.prefix or "VIRTBANK",bank_num+1)
            if args.dump=='syx':
                dump_file+='.syx'
            else:
                dump_file+='.bin'

            print("  {}   -> {}".format(bank_name,dump_file))
            dump_bank(bank_data,dump_file)


#--------------------
# main body
#--------------------

if __name__ == '__main__':

    # parse arguments

    parser = argparse.ArgumentParser(description="Dump program banks or individual programs from an SQ80 disk dump file as either literal binary, or SYSEX format. File names for the dump files are automatically generated from the bank/program number and name stored in the disk directory.")
    parser.add_argument('imagefile',type=argparse.FileType('rb') ,help='The source SQ80 disk image file')
    parser.add_argument('mode',choices=['bank','prog','virtbank'],help='bank: Program bank mode. Dump/list one or all of the 40 program banks.        prog: Single program mode. Dump/list one or all of the 128 single programs as individual files.     virtbank: Virtual bank mode. Dump/list the 128 single programs as up to 5 virtual banks. Empty program positions in the virtual banks are filled using an init patch with a blank name.\n')
    #parser.add_argument('--indiv','-i',help='',action='store_true')
    parser.add_argument('--number','-n',type=int,help='The number of the bank/prog/virtbank to list or dump. Otherwise all will be dumped.')
    parser.add_argument('--dump','-d',help='Actually dump the banks/programs/virtbanks (otherwise they are only listed). The parameter should be either "syx" or "bin". "syx" is a SYSEX file that can be output straight to the SQ80 via a midi port. "bin" is a literal binary dump of the bank/program.',choices=['syx','bin'])
    parser.add_argument('--prefix','-p',help='Prefix to add to output filenames. Can specify directories than the current using a / in the prefix',action='store')
    parser.add_argument('--list','-l',help='Used to generate listings of programs on a disk in a more concise format (5 programs per line). Can be used in bank mode to list the programs within each bank. Virtbank mode uses the concise format by default, so this flag does nothing.',action='store_true')

    args = parser.parse_args()
    if args.number == 0 :
        raise RuntimeError("banks/programs count from 1 upwards")

    if args.list and args.dump:
        raise RuntimeError("Cannot select --list and --dump at the same time.")

    # check disk image file

    header=args.imagefile.read(10)
    if (header != b'!SQ80DISK!'):
        raise RuntimeError("Doesn't appear to be a valid SQ80 dump file")

    # read directory

    directory_buf=bytearray()

    for (c,h,s) in [(0,0,5),(0,1,5),(1,1,5),(1,0,5)]:
        args.imagefile.seek(chs_to_offset(c,h,s))
        directory_buf+=args.imagefile.read(512)

    directory=directory(directory_buf)

    print("SQ80 Disk Image File:",args.imagefile.name)

    if args.mode == 'prog':
        mode_prog()
    elif args.mode == 'bank':
        mode_bank()
    elif args.mode == 'virtbank':
        mode_virtbank()
