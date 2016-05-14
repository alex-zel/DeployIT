import os
import sys
import glob
import platform
import subprocess
import json

execution_dir = os.path.normpath(os.path.dirname(sys.argv[0]))
help_txt = os.path.join(execution_dir, 'help.txt')
config_file = os.path.join(execution_dir, 'config', 'config.txt')


def print_help():
    """
    print help text
    :return: none
    """
    with open(help_txt, 'r') as infile:
        for line in infile:
            print(line)


def extra_strip(the_string, extra=0):
    """
    Remove unwanted chars from shell commands output
    :param the_string: string
    :param extra: extra chars/strings to remove
    :return: string
    """
    replace_chars = ['b\'', '\\r', '\\n', '\'', ' : ']
    if extra:
        replace_chars.extend(extra)
    for char in replace_chars:
        the_string = the_string.replace(char, '')
    return the_string


def arg_parse():
    """
    Parse arguments and check for any errors.
    :return: arguments as dictionary {arg_name: arg_value ... }
    """
    # mandatory arguments
    expected_arguments = ['iso-path',
                          'partition']
    # optional arguments
    optional_arguments = ['arch',
                          'help',
                          'disk',
                          'edition',
                          'hostname',
                          'unattended']

    if '--help' in sys.argv[1:] or len(sys.argv) == 1:
        print_help()
        sys.exit()
    try:
        arguments = {arg.split(':')[0].replace('--', ''): arg.split(':', maxsplit=1)[1]     # split and remove symbols
                     for arg in sys.argv[1:]                                                # iterate over system arguments
                     if arg.split(':', maxsplit=1)[1] is not '' and                         # check if arg is valid
                     arg.split(':')[0].replace('--', '') in expected_arguments + optional_arguments}
    except IndexError:
        print('Bad input, check syntax')
        sys.exit()

    # ensure all mandatory arguments are present
    if any(arg not in arguments for arg in expected_arguments):
        print('Missing some required arguments, please consult usage guide.')
        print_help()
        sys.exit()
    # check that custom unattended file is reachable (if provided)
    elif 'unattended' in arguments and not os.path.isfile(arguments['unattended']):
        print('Unattended file is unreachable, check path and ensure file is present')
        sys.exit()

    return arguments


def load_config():
    """
    Load configuration file in json format
    Expected vars:
                    default ISO location

    :return: config as dict
    """
    try:
        with open(config_file, 'r') as infile:
            the_config = {line.split('=')[0]: line.split('=')[1].replace('\n', '') for line in infile.readlines()}
    except FileNotFoundError:
        print('Config file not found, aborting.')
        sys.exit()
    return the_config


def get_win_iso(iso_path, win_release):
    """
    Parse win_release to find matching ISO files in provided iso_path (recursive).
    Matching win_release to iso takes into account the whole path, not only file name.
    :param iso_path: string, path to ISO directory
    :param win_release: string, 'server 2012 r2' 'rs 14316 x64'
    :return: list of matches
    """
    filepaths = [filepath for filepath in glob.iglob(r'%s\**\*.iso' % iso_path, recursive=True)]
    matches = [filepath for filepath in filepaths
               if all(chk.lower() in filepath.lower() for chk in win_release.split(' '))]
    return matches


def get_editions(mount_path):
    """
    Get windows editions in mounted installation disk.
    :param mount_path: path to install.wim
    :return: editions as dictionary
    """
    # values to look for in command output
    values = ['Index', 'Description']
    # run dism command
    proc = subprocess.Popen(['Dism', '/Get-WimInfo', '/WimFile:%s' % mount_path], stdout=subprocess.PIPE, shell=True)
    # strip all unwanted lines and characters
    out = [extra_strip(line, values) for line in str(proc.communicate()[0]).split('\\n') if any(val in extra_strip(line) for val in values)]
    # return list in dictionary format
    return {out[i]: out[i+1] for i in range(0, len(out), 2)}


def unattended_prep(unattended_path, hostname, disk_id, part_id, edition):
    """
    Prepare unattended file for deployment, search and replace required values in unattended file
    :param unattended_path: path to unattended file
    :param hostname: new hostname
    :param disk_id: disk ID to install to
    :param part_id: partition ID to install to
    :param edition: windows edition name
    :return: path to new unattended file
    """
    temp = r'' + os.environ['temp']
    replace_patterns = {'diskid': disk_id,
                        'partitionid': part_id,
                        'wineditionname': edition,
                        'newhostname': hostname}
    # open original file
    with open(unattended_path, 'r') as infile:
        unattended = infile.read()
    # search and replace values
    for pattern in replace_patterns:
        unattended = unattended.replace(pattern, replace_patterns[pattern])
    # save new file
    with open(os.path.join(temp, 'unattended.xml'), 'w') as outfile:
        outfile.write(unattended)

    return os.path.join(temp, 'unattended.xml')


def iso_mount(iso_path, umount=0):
    """
    Mount ISO image using powershell and grab drive letter on of mounted ISO.
    :param iso_path: path to ISO file
    :param umount: un-mount image
    :return: drive letter (single char)
    """
    if not umount:
        proc = subprocess.Popen(['C:/windows/system32/WindowsPowerShell/v1.0/powershell.exe',
                                 '(Mount-DiskImage %s -PassThru | Get-Volume).DriveLetter' % os.path.normpath(iso_path)],
                                stdout=subprocess.PIPE, shell=True)
        out = str(proc.communicate()[0])
        return extra_strip(out)
    else:
        subprocess.Popen(['C:/windows/system32/WindowsPowerShell/v1.0/powershell.exe', 'Dismount-DiskImage', iso_path], stdout=subprocess.PIPE, shell=True)
        return


def get_partition_index(volume_label):
    """
    Get partition and disk number based on volume label using powershell
    There is a problem with gow powershell enumerates partitions on basic disks, if there is a primary partition after a logical one,
    it will be counted as being before the extended partition and will mess up the count, hence we will be enumerating the partitions based on offset (excluding the extended one)
    :param volume_label: partition name string
    :return: partition, disk index as tuple
    """
    # powershell command to collect information about all disks and partitions
    command = 'ConvertTo-Json -Depth 4 @(foreach ($disk in (Get-Partition).DiskNumber | select -Unique | Sort-Object){' \
              '@{' \
              '$disk.ToString() = foreach ($part in (Get-Partition -DiskNumber $disk | where {$_.Type -notlike \'*Extended\'}).PartitionNumber | Sort-Object){' \
              '@{' \
              '(Get-Partition -DiskNumber $disk -PartitionNumber $part).Offset.ToString() = Get-Partition -DiskNumber $disk -PartitionNumber $part | ForEach-Object {' \
              '@{' \
              'PartitionNumber=$_.PartitionNumber;' \
              'DriveLetter=$_.DriveLetter;' \
              'Offset=$_.Offset;' \
              'FileSystemLabel = if ($_.DriveLetter){(Get-Volume -DriveLetter (Get-Partition -DiskNumber $disk -PartitionNumber $part).DriveLetter).FileSystemLabel} ' \
              'else {""}}}}}}})'
    # strip control characters and convert to json
    proc = subprocess.Popen('C:/windows/system32/WindowsPowerShell/v1.0/powershell.exe %s' % command, stdout=subprocess.PIPE)
    out = json.loads(str(proc.communicate()[0]).replace('\\r\\n', '')[2:-1])
    # parse received json object into dictionary
    disks = {disk:
             {out[disk][str(disk)][parts][str(part)]['Offset']: out[disk][str(disk)][parts][str(part)] for parts in range(0, len(out[disk][str(disk)]))
              for part in out[disk][str(disk)][parts]} for disk in range(0, len(out))}
    # order partitions based on offset
    for disk in disks:
        for offset in sorted(disks[disk]):
            index = sorted(disks[disk]).index(offset)
            disks[disk][index+1] = disks[disk].pop(offset)
    # check if given volume label is an actual partition
    for disk in disks:
        for part in disks[disk]:
            if volume_label == disks[disk][part]['FileSystemLabel']:
                partition_id = part
                disk_id = disk

    if partition_id == '':
        print('No such partition, please check volume label')
        sys.exit()
    if disk_id == '':
        print('No such disk, please check volume label')
        sys.exit()
    return str(partition_id), str(disk_id)


def main():
    # check arguments and load config file
    arguments = arg_parse()
    config = load_config()

    # check unattended file is present
    if not os.path.isfile(os.path.join(execution_dir, config['default_unattended'])):
        print('Unattended file is missing, please check config file.')
        sys.exit()

    # ensure iso disk is available
    if not os.path.exists(arguments['iso-path']):
        arguments['iso-path'] = get_win_iso(config['ISO_path'], arguments['iso-path'])
        if len(arguments['iso-path']) == 0:
            print('No such file/release, quiting')
            sys.exit()
        if len(arguments['iso-path']) > 1:
            print('Not specific enough, please select Windows release from below:')
            win_releases = {str(x): arguments['iso-path'][x] for x in range(0, len(arguments['iso-path']))}
            for release in sorted(win_releases):
                print('%s %s' % (release, win_releases[release].split('\\')[-1]))
            while True:
                select = input('Select release number: ')
                if select in win_releases:
                    arguments['iso-path'] = win_releases[select]
                    break
                print('No such release, try again')
        arguments['iso-path'] = arguments['iso-path'][0]

    # mount iso and get mount drive
    mount_drive = iso_mount(arguments['iso-path']) + ':/'

    '''
        check if edition name was provided,
        if not, get all available editions from ISO and present to user for selection,
        if only 1 edition is available then use it without prompt.
    '''
    if 'edition' not in arguments:
        editions = get_editions(os.path.join(mount_drive, 'sources', 'install.wim'))
        if len(editions) == 1:
            arguments['edition'] = editions['1']
        else:
            print('No editions specified, please choose from following available editions')
            for edition in sorted(editions):
                print('%s - %s' % (edition, editions[edition]))
            while True:
                index = input('Choose edition: ')
                if index in editions:
                    arguments['edition'] = index
                    break
                else:
                    print('No such edition, choose again')

    # get OS architecture
    os_arch = platform.architecture()[0].replace('bit', '')
    # get partition/disk info
    partition_index = get_partition_index(arguments['partition'])
    # prepare unattended file for installation
    unattended_path = unattended_prep(os.path.join(execution_dir, config['default_unattended']) if 'unattended' not in arguments else arguments['unattended'],
                                      arguments['hostname'] if 'hostname' in arguments else platform.node(),
                                      partition_index[1],
                                      partition_index[0],
                                      arguments['edition'])

    # execute setup.exe
    subprocess.call(['C:/windows/system32/WindowsPowerShell/v1.0/powershell.exe',
                     'Format-Volume', '-FileSystemLabel', arguments['partition'], '-NewFileSystemLabel', arguments['partition'], '-confirm:$false'])
    install = subprocess.Popen([os.path.join(mount_drive, 'sources', 'setup.exe'), '-noreboot', '-unattend:%s' % unattended_path])
    install.wait()
    iso_mount(arguments['iso-path'], umount=True)
    subprocess.call(['shutdown', '-r', '-t', '0'])
    return

if __name__ == '__main__':
    main()
