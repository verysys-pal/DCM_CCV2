TOP=../..

include $(TOP)/configure/CONFIG
#----------------------------------------
#  ADD MACRO DEFINITIONS AFTER THIS LINE
#=============================

#=============================
# Build the IOC application

PROD_IOC = DCM_CCV2
# DCM_CCV2.dbd will be created and installed
DBD += DCM_CCV2.dbd

# DCM_CCV2.dbd will be made up from these files:
DCM_CCV2_DBD += base.dbd

# Include dbd files from all support applications:
#DCM_CCV2_DBD += xxx.dbd

# Add all the support libraries needed by this IOC
#DCM_CCV2_LIBS += xxx

# DCM_CCV2_registerRecordDeviceDriver.cpp derives from DCM_CCV2.dbd
DCM_CCV2_SRCS += DCM_CCV2_registerRecordDeviceDriver.cpp

# Build the main IOC entry point on workstation OSs.
DCM_CCV2_SRCS_DEFAULT += DCM_CCV2Main.cpp
DCM_CCV2_SRCS_vxWorks += -nil-

# Add support from base/src/vxWorks if needed
#DCM_CCV2_OBJS_vxWorks += $(EPICS_BASE_BIN)/vxComLibrary

# Finally link to the EPICS Base libraries
DCM_CCV2_LIBS += $(EPICS_BASE_IOC_LIBS)

#===========================

include $(TOP)/configure/RULES
#----------------------------------------
#  ADD RULES AFTER THIS LINE

