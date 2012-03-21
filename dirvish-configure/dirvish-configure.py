#!/usr/bin/python

import yaml
import subprocess
import StringIO
import os
import sys
import difflib
from optparse import OptionParser

parser = OptionParser()
parser.add_option('-d', '--debug', action='store_true',
                default=False, help="Debug output")
parser.add_option('-y', '--yes', action='store_true',
                default=False, help="Always answer yes to questions (USE WITH CAUTION)")
parser.add_option('-v', '--verbose', action='store_true',
                default=False, help="Show all checked backups")

(options, args) = parser.parse_args()

def print_debug(msg):
    if options.debug == True:
        print msg

def run_command(cmd):
    print(cmd)
    if not options.debug == True:
        subprocess.call(cmd, shell=True) 

def print_verbose(msg):
    if options.verbose == True:
        print msg

dirvish_conf_path = '/etc/dirvish'
config_data = yaml.load(file('/etc/dirvish/dirvish.yaml', 'r'))

list_banks = []
list_vaults = []

for host in config_data['hosts']:
    hostname = '%s.%s' % (host['host'], host['domain'])
    #hostname_filename = '%s_%s' % (host['host'], host['domain'].replace('.','_'))
    hostname_filename = hostname

    for backup in host['backups']:
        #lvmname = '%s-%s' % (hostname_filename, backup['name'])
        lvmname = '%s_%s' % (hostname_filename, backup['name'])
        backup_name = '%s_%s' % (host['host'], backup['name'])
        backup_path = '/backups/%s/%s' % (hostname_filename, backup_name)
        backup_device = '/dev/%s/%s' % (backup['volumegroup'], lvmname)
        dirvish_config = StringIO.StringIO()

        print_verbose('Host: %s.%s' % (host['host'], host['domain']))
        print_verbose('Backup: %s' % backup['name'])
        #print 'Mount: /dev/%s/%s -> %s' % (backup['volumegroup'], lvmname, backup_path)

        print_debug('checking if logical volume exists: %s' % lvmname)
        lvm,lvmerr = subprocess.Popen('find /dev/%s -name %s' % (backup['volumegroup'], lvmname), shell=True, stdout=subprocess.PIPE).communicate()
        if lvm is '':
            print_debug("I don't think the logical volume exists!?")
            question_create = raw_input("Create the LV? [y/N]")
            if question_create == 'y':
                question_size = raw_input("Size of the LV? [e.g. 10G]")
                if question_size == '':
                    question_size = "5G"
                run_command('lvcreate --size %s --name %s %s' % (question_size, lvmname, backup['volumegroup']))
                run_command('mkfs.ext3 %s' % backup_device)
            else:
                continue
        
        print_debug('looking for entry in /etc/fstab')
        fstabs = open('/etc/fstab', 'r').readlines()
        found_fstab = False
        for fstab in fstabs:
            if fstab.split(' ')[0] == backup_device:
                print_debug('found it!')
                found_fstab = True
                print_debug(repr(fstab))
                if fstab.split(' ')[1] != backup_path:
                    print_debug('but its not right..')
                else:
                    print_debug('and its correctly!')
        if found_fstab == False:
            print_debug('must not be fstabbed..')
            question_fstab = raw_input("Create the fstab entry? [y/N]")
            if question_fstab == 'y':
                run_command('echo "%s %s ext3 defaults 1 2" >> /etc/fstab' % (backup_device, backup_path))
            else:
                continue
        
        print_debug('looking for mount')
        mounts = open('/proc/mounts', 'r').readlines()
        found_mount = False
        for mount in mounts:
            #print repr(mount.split(' ')[0]), repr('/dev/%s/%s' % (backup['volumegroup'], lvmname))
            if mount.split(' ')[0] == backup_device:
                print_debug('found it!')
                found_mount = True
                print_debug(repr(mount))
                if mount.split(' ')[1] != backup_path:
                    print_debug('but its not right..')
                else:
                    print_debug('and mounted correctly!')
        if found_mount == False:
            print_debug('must not be mounted..')
            question_mount = raw_input("Mount the filesystem? [y/N]")
            if question_mount == 'y':
                run_command('mkdir -p %s' % backup_path)
                run_command('mount %s' % backup_path)
            else:
                continue

        print_debug('now looking for dirvish config at %s/dirvish' % backup_path)
        if os.path.exists('%s/dirvish' % backup_path):
            print_debug('there it is')
        else:
            print_debug('it appears the dirvish config path does not exist..')
            question_createdirvish = raw_input("Create dirvish configuration files? [y/N]")
            if question_createdirvish == 'y':
                run_command('mkdir %s/dirvish' % backup_path)
        if os.path.isfile('%s/dirvish/default.conf' % backup_path):
            print_debug('found the default.conf file')
        else:
            print_debug('nuts, cant find teh file')

        print_debug('building what i think is the config file')
        #print >>dirvish_config, 'Config file: %s/dirvish/dirvish.conf' % (backup_path)
        print >>dirvish_config, 'client: root@%s\ntree: %s' % (hostname, backup['remotepath'])
        try:
            for host_k,host_v in host['extra'].items():
                if type(host_v) is list:
                    print >>dirvish_config, '%s: ' % (host_k)
                    for val in host_v:
                        print >>dirvish_config, ' %s' % val
                else:
                    print >>dirvish_config, '%s: %s' % (host_k, host_v)
        except KeyError:
            pass
        try:
            for backup_k,backup_v in backup['extra'].items():
                if type(backup_v) is list:
                    print >>dirvish_config, '%s: ' % (backup_k)
                    for val in backup_v:
                        print >>dirvish_config, ' %s' % val
                else:
                    print >>dirvish_config, '%s: %s' % (backup_k, backup_v)
        except KeyError:
            pass

        print_debug('looking for existing config file..')
        try:
            backup_conf = open('%s/dirvish/default.conf' % backup_path).readlines()
        except IOError:
            print_debug('config file not there!?!! okay using nothing')
            backup_conf = []

        print_debug('diffing existing config with what I generated..')
        #print backup_conf
        #print dirvish_config.getvalue().splitlines(True)
        diff_lines = 0
        diff = StringIO.StringIO()
        for line in difflib.unified_diff(backup_conf, dirvish_config.getvalue().splitlines(True),fromfile='%s/dirvish/default.conf' % backup_path,tofile='dconf.py'):
            diff.write(line)
            diff_lines = diff_lines + 1
        if diff_lines > 0:
            sys.stdout.write(diff.getvalue())
            question_configdiff = raw_input("Replace existing config with generated one? [y/N]")
            if question_configdiff == 'y':
                run_command('mv %s/dirvish/default.conf %s/dirvish/default.conf.bak 1>/dev/null 2>/dev/null' % (backup_path, backup_path))
                print 'writing conf to %s/dirvish/default.conf' % backup_path
                write_conf = open('%s/dirvish/default.conf' % backup_path, 'w')
                write_conf.writelines(dirvish_config.getvalue())
                write_conf.close()
            else:
                continue
        else:
            print_debug('config file looks good!')

        print_debug('okay, have we run dirvish befoer?')
        if os.path.isfile('%s/dirvish/default.hist' % backup_path):    
            print_debug('wow this looks like a legit backup and everything..' )
        else:
            print_debug('looks blank... prob need to run init..')
            print 'Run: dirvish --vault %s --init' % backup_name
        print_verbose('This backup is configured correctly')
        bank = '/backups/%s' % (hostname_filename)
        if bank not in list_banks:
            list_banks.append('/backups/%s' % (hostname_filename))
        list_vaults.append(backup_name)

print_debug('add banks and vaults in')
banks = StringIO.StringIO()
vaults = StringIO.StringIO()
print >>banks, 'bank:'
for bank in list_banks:
    print >>banks, ' %s' % bank

print >>vaults, 'Runall:'
for vault in list_vaults:
    print >>vaults, ' %s' % vault

write_banks = open('%s/bank.conf' % dirvish_conf_path, 'w')
write_banks.writelines(banks.getvalue())
write_banks.close()
write_vaults = open('%s/vault.conf' % dirvish_conf_path, 'w')
write_vaults.writelines(vaults.getvalue())
write_vaults.close()

