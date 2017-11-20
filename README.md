DeployIT Ver 1.0.0
Developed by Alex Zeleznikov
This program is built for windows deployment using ISO setup image, for the purpose of automating the installation process.

Build Instructions:

    1.	Install python 3.5
    2.	Install "Microsoft Visual C++ 2010 SP1 Redistributable Package" from either of the links (arch is dependent on python arch you installed)
        http://www.microsoft.com/en-us/download/details.aspx?id=8328 - 32 bit
        http://www.microsoft.com/en-us/download/details.aspx?id=13523 - 64 bit
    3.	Ensure these commands work in command prompt: python, pip. If the commands do not work, add the following to your PATH environmental variable: C:\Python34  and  C:\Python34\Scripts
    4.	Open command prompt in DeployIT directory
    5.	Run “pip install –r requirements.txt”, if the command hangs and won’t download anything, try adding –-proxy=YOUR_PROXY and run again
    6.  Run "python setup.py"
    7.	If all goes well you should see a folder named DeployIT created, cd to it
    8.	Last thing is to provide default unattended files for x64/x32 architectures, see below on how to prepare this files, place both these files in the data\ folder, naming them autounattend_64.xml and autounattend_32.xml

Notes:
	Microsoft Visual C++ 2010 SP1 Redistributable Package is required for clients to run the program.

Documentation:

    --iso-path: Mandatory
        Two options are present, provide full path to ISO installation image, path must not have any spaces (issue with PowerShell command),
        or, write name of windows release based on iso filename, for example say you have an ISO named "en_windows_8_enterprise_x64_dvd_917522.iso",
        you can either provide the full path, or write "win 8 x64", keep in mind that is other files match, you'll be prompted to select 1 from all matches.

    --partition: Mandatory
        Partition name (volume label) of partition to install ISO to, disk ID is resolved using volume label.

    --hostname: Optional
        New hostname for installation, defaults to current hostname.

    --edition: Optional
        Windows edition name (in case of multiple editions in ISO), if omitted;
        If only one edition if present in ISO, it will be used automatically,
        If more than one edition is present, selection if presented to user with available releases.

    --unattended: Optional
        Custom unattended file path, if omitted, defaults to local unattended file (located at data\unattended_64/32.xml)

    --help: Optional
        Print help massage 

Unattended prep:
    Unattended files can be configured freely, except for  the following keywords which are replaced during deployment::
    •	Hostname - <ComputerName>newhostname</ComputerName>
    •	Disk ID - <DiskID>diskid</DiskID>
    •	Partition ID - PartitionID>partitionid</PartitionID>
    •	Windows edition - <Value>wineditionname</Value>
    These values need to be replaces with their corresponding keys for automation to work properly.
