#!../../bin/linux-x86_64/DCM_CCV2

#- You may have to change DCM_CCV2 to something else
#- everywhere it appears in this file

< envPaths

cd "${TOP}"

## Register all support components
dbLoadDatabase "dbd/DCM_CCV2.dbd"
DCM_CCV2_registerRecordDeviceDriver pdbbase

## Load record instances (use absolute TOP path to ensure correct file)
dbLoadRecords("${TOP}/db/dcm_cryo.db")

#drvAsynIPPortConfigure("portName", "hostInfo", 0, 0, 0)
cd "${TOP}/iocBoot/${IOC}"
iocInit

## Start any sequence programs
#seq sncxxx,"user=root"
