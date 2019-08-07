CREATE ALGORITHM=UNDEFINED DEFINER=`sa_server`@`localhost` SQL SECURITY DEFINER VIEW `view_number_bis` AS select `a`.`name` AS `room_name`,`b`.`name` AS `bed_name`,`c`.`file_basename` AS `file_basename`,`d`.`id` AS `id`,DATE_ADD(`d`.`dt`, INTERVAL 9 HOUR) AS `dt`,`d`.`BIS` AS `BIS`,`d`.`EMG` AS `EMG`,`d`.`SR` AS `SR`,`d`.`SEF` AS `SEF`,`d`.`SQI` AS `SQI`,`d`.`TOTPOW` AS `TOTPOW` from (((`sa_api_room` `a` join `sa_api_bed` `b`) join `sa_api_filerecorded` `c`) join `number_bis` `d` on(((`a`.`id` = `b`.`room_id`) and (`b`.`id` = `c`.`bed_id`) and (`c`.`id` = `d`.`record_id`))));
CREATE ALGORITHM=UNDEFINED DEFINER=`sa_server`@`localhost` SQL SECURITY DEFINER VIEW `view_number_dcq` AS select `a`.`name` AS `room_name`,`b`.`name` AS `bed_name`,`c`.`file_basename` AS `file_basename`,`d`.`id` AS `id`,DATE_ADD(`d`.`dt`, INTERVAL 9 HOUR) AS `dt`,`d`.`CI` AS `CI`,`d`.`CO` AS `CO`,`d`.`FTc` AS `FTc`,`d`.`FTp` AS `FTp`,`d`.`HR` AS `HR`,`d`.`MA` AS `MA`,`d`.`MD` AS `MD`,`d`.`PV` AS `PV`,`d`.`SD` AS `SD`,`d`.`SV` AS `SV`,`d`.`SVI` AS `SVI` from (((`sa_api_room` `a` join `sa_api_bed` `b`) join `sa_api_filerecorded` `c`) join `number_dcq` `d` on(((`a`.`id` = `b`.`room_id`) and (`b`.`id` = `c`.`bed_id`) and (`c`.`id` = `d`.`record_id`))));
CREATE ALGORITHM=UNDEFINED DEFINER=`sa_server`@`localhost` SQL SECURITY DEFINER VIEW `view_number_eev` AS select `a`.`name` AS `room_name`,`b`.`name` AS `bed_name`,`c`.`file_basename` AS `file_basename`,`d`.`id` AS `id`,DATE_ADD(`d`.`dt`, INTERVAL 9 HOUR) AS `dt`,`d`.`ADBP` AS `ADBP`,`d`.`ART_MBP` AS `ART_MBP`,`d`.`ART_MBP_INT` AS `ART_MBP_INT`,`d`.`ASBP` AS `ASBP`,`d`.`BT_INT` AS `BT_INT`,`d`.`BT_PA` AS `BT_PA`,`d`.`CDBP` AS `CDBP`,`d`.`CFI_INT` AS `CFI_INT`,`d`.`CI` AS `CI`,`d`.`CI_STAT` AS `CI_STAT`,`d`.`CMBP` AS `CMBP`,`d`.`CO` AS `CO`,`d`.`CO_STAT` AS `CO_STAT`,`d`.`CSBP` AS `CSBP`,`d`.`CVP` AS `CVP`,`d`.`CVP_INT` AS `CVP_INT`,`d`.`DO2` AS `DO2`,`d`.`EDV` AS `EDV`,`d`.`EDVI` AS `EDVI`,`d`.`EDVI_INT` AS `EDVI_INT`,`d`.`EDVI_STAT` AS `EDVI_STAT`,`d`.`EDV_INT` AS `EDV_INT`,`d`.`EDV_STAT` AS `EDV_STAT`,`d`.`EF_INT` AS `EF_INT`,`d`.`ESV` AS `ESV`,`d`.`ESVI` AS `ESVI`,`d`.`EVLWI_INT` AS `EVLWI_INT`,`d`.`EVLW_INT` AS `EVLW_INT`,`d`.`HR` AS `HR`,`d`.`HR_AVG` AS `HR_AVG`,`d`.`HR_INT` AS `HR_INT`,`d`.`ICI` AS `ICI`,`d`.`ICI_AVG` AS `ICI_AVG`,`d`.`ICO` AS `ICO`,`d`.`ICO_AVG` AS `ICO_AVG`,`d`.`INPUT_HB` AS `INPUT_HB`,`d`.`INPUT_SPO2` AS `INPUT_SPO2`,`d`.`ITBVI_INT` AS `ITBVI_INT`,`d`.`ITBV_INT` AS `ITBV_INT`,`d`.`O2EI` AS `O2EI`,`d`.`RVEF` AS `RVEF`,`d`.`RVEF_STAT` AS `RVEF_STAT`,`d`.`SAO2` AS `SAO2`,`d`.`SCVO2` AS `SCVO2`,`d`.`SNR` AS `SNR`,`d`.`SQI` AS `SQI`,`d`.`SV` AS `SV`,`d`.`SVI` AS `SVI`,`d`.`SVI_STAT` AS `SVI_STAT`,`d`.`SVO2` AS `SVO2`,`d`.`SVR` AS `SVR`,`d`.`SVRI` AS `SVRI`,`d`.`SVV` AS `SVV`,`d`.`SV_STAT` AS `SV_STAT`,`d`.`VO2` AS `VO2`,`d`.`VO2I_INT` AS `VO2I_INT` from (((`sa_api_room` `a` join `sa_api_bed` `b`) join `sa_api_filerecorded` `c`) join `number_eev` `d` on(((`a`.`id` = `b`.`room_id`) and (`b`.`id` = `c`.`bed_id`) and (`c`.`id` = `d`.`record_id`))));
CREATE ALGORITHM=UNDEFINED DEFINER=`sa_server`@`localhost` SQL SECURITY DEFINER VIEW `view_number_gec` AS select `a`.`name` AS `room_name`,`b`.`name` AS `bed_name`,`c`.`file_basename` AS `file_basename`,`d`.`id` AS `id`,DATE_ADD(`d`.`dt`, INTERVAL 9 HOUR) AS `dt`,`d`.`ABP_SBP` AS `ABP_SBP`,`d`.`ABP_DBP` AS `ABP_DBP`,`d`.`ABP_MBP` AS `ABP_MBP`,`d`.`ABP_HR` AS `ABP_HR`,`d`.`AGENT_ET` AS `AGENT_ET`,`d`.`AGENT_FI` AS `AGENT_FI`,`d`.`AGENT_IN` AS `AGENT_IN`,`d`.`AGENT_MAC` AS `AGENT_MAC`,`d`.`ARRH_ECG_HR` AS `ARRH_ECG_HR`,`d`.`BAL_GAS_ET` AS `BAL_GAS_ET`,`d`.`BIS_BIS` AS `BIS_BIS`,`d`.`BIS_BSR` AS `BIS_BSR`,`d`.`BIS_EMG` AS `BIS_EMG`,`d`.`BIS_SQI` AS `BIS_SQI`,`d`.`BT_AXIL` AS `BT_AXIL`,`d`.`BT_PA` AS `BT_PA`,`d`.`BT_ROOM` AS `BT_ROOM`,`d`.`CO` AS `CO`,`d`.`COMPLIANCE` AS `COMPLIANCE`,`d`.`CO2_AMB_PRESS` AS `CO2_AMB_PRESS`,`d`.`CO2_ET` AS `CO2_ET`,`d`.`CO2_ET_PERCENT` AS `CO2_ET_PERCENT`,`d`.`CO2_FI` AS `CO2_FI`,`d`.`CO2_RR` AS `CO2_RR`,`d`.`CO2_IN` AS `CO2_IN`,`d`.`CO2_IN_PERCENT` AS `CO2_IN_PERCENT`,`d`.`CVP` AS `CVP`,`d`.`ECG_HR` AS `ECG_HR`,`d`.`ECG_HR_ECG` AS `ECG_HR_ECG`,`d`.`ECG_HR_MAX` AS `ECG_HR_MAX`,`d`.`ECG_HR_MIN` AS `ECG_HR_MIN`,`d`.`ECG_IMP_RR` AS `ECG_IMP_RR`,`d`.`ECG_ST` AS `ECG_ST`,`d`.`ECG_ST_AVF` AS `ECG_ST_AVF`,`d`.`ECG_ST_AVL` AS `ECG_ST_AVL`,`d`.`ECG_ST_AVR` AS `ECG_ST_AVR`,`d`.`ECG_ST_I` AS `ECG_ST_I`,`d`.`ECG_ST_II` AS `ECG_ST_II`,`d`.`ECG_ST_III` AS `ECG_ST_III`,`d`.`ECG_ST_V` AS `ECG_ST_V`,`d`.`EEG_FEMG` AS `EEG_FEMG`,`d`.`ENT_BSR` AS `ENT_BSR`,`d`.`ENT_EEG` AS `ENT_EEG`,`d`.`ENT_EMG` AS `ENT_EMG`,`d`.`ENT_RD_BSR` AS `ENT_RD_BSR`,`d`.`ENT_RD_EEG` AS `ENT_RD_EEG`,`d`.`ENT_RD_EMG` AS `ENT_RD_EMG`,`d`.`ENT_RE` AS `ENT_RE`,`d`.`ENT_SE` AS `ENT_SE`,`d`.`ENT_SR` AS `ENT_SR`,`d`.`EPEEP` AS `EPEEP`,`d`.`FEM_SBP` AS `FEM_SBP`,`d`.`FEM_DBP` AS `FEM_DBP`,`d`.`FEM_MBP` AS `FEM_MBP`,`d`.`FEM_HR` AS `FEM_HR`,`d`.`HR` AS `HR`,`d`.`ICP` AS `ICP`,`d`.`IE_RATIO` AS `IE_RATIO`,`d`.`LAP` AS `LAP`,`d`.`MAC_AGE` AS `MAC_AGE`,`d`.`MV` AS `MV`,`d`.`N2O_ET` AS `N2O_ET`,`d`.`N2O_FI` AS `N2O_FI`,`d`.`N2O_IN` AS `N2O_IN`,`d`.`NIBP_DBP` AS `NIBP_DBP`,`d`.`NIBP_SBP` AS `NIBP_SBP`,`d`.`NIBP_HR` AS `NIBP_HR`,`d`.`NIBP_MBP` AS `NIBP_MBP`,`d`.`NMT_CURRENT` AS `NMT_CURRENT`,`d`.`NMT_PTC_CNT` AS `NMT_PTC_CNT`,`d`.`NMT_PULSE_WIDTH` AS `NMT_PULSE_WIDTH`,`d`.`NMT_T1` AS `NMT_T1`,`d`.`NMT_T4_T1` AS `NMT_T4_T1`,`d`.`NMT_TOF_CNT` AS `NMT_TOF_CNT`,`d`.`O2_ET` AS `O2_ET`,`d`.`O2_FE` AS `O2_FE`,`d`.`O2_FI` AS `O2_FI`,`d`.`PA_SBP` AS `PA_SBP`,`d`.`PA_DBP` AS `PA_DBP`,`d`.`PA_MBP` AS `PA_MBP`,`d`.`PA_HR` AS `PA_HR`,`d`.`PCWP` AS `PCWP`,`d`.`PEEP` AS `PEEP`,`d`.`PLETH_HR` AS `PLETH_HR`,`d`.`PLETH_IRAMP` AS `PLETH_IRAMP`,`d`.`PLETH_SPO2` AS `PLETH_SPO2`,`d`.`PPEAK` AS `PPEAK`,`d`.`PPLAT` AS `PPLAT`,`d`.`PPV` AS `PPV`,`d`.`RAP` AS `RAP`,`d`.`RR` AS `RR`,`d`.`RR_VENT` AS `RR_VENT`,`d`.`RVEF` AS `RVEF`,`d`.`RVP` AS `RVP`,`d`.`SPI` AS `SPI`,`d`.`SPV` AS `SPV`,`d`.`TOF_T1` AS `TOF_T1`,`d`.`TOF_T2` AS `TOF_T2`,`d`.`TOF_T3` AS `TOF_T3`,`d`.`TOF_T4` AS `TOF_T4`,`d`.`TV_EXP` AS `TV_EXP`,`d`.`TV_INSP` AS `TV_INSP` from (((`sa_api_room` `a` join `sa_api_bed` `b`) join `sa_api_filerecorded` `c`) join `number_gec` `d` on(((`a`.`id` = `b`.`room_id`) and (`b`.`id` = `c`.`bed_id`) and (`c`.`id` = `d`.`record_id`))));
CREATE ALGORITHM=UNDEFINED DEFINER=`sa_server`@`localhost` SQL SECURITY DEFINER VIEW `view_number_inv` AS select `a`.`name` AS `room_name`,`b`.`name` AS `bed_name`,`c`.`file_basename` AS `file_basename`,`d`.`id` AS `id`,DATE_ADD(`d`.`dt`, INTERVAL 9 HOUR) AS `dt`,`d`.`AUC_L` AS `AUC_L`,`d`.`AUC_R` AS `AUC_R`,`d`.`BASELINE_L` AS `BASELINE_L`,`d`.`BASELINE_R` AS `BASELINE_R`,`d`.`SCO2_L` AS `SCO2_L`,`d`.`SCO2_R` AS `SCO2_R`,`d`.`SCO2_S1` AS `SCO2_S1`,`d`.`SCO2_S2` AS `SCO2_S2`,`d`.`rSO2_L` AS `rSO2_L`,`d`.`rSO2_R` AS `rSO2_R` from (((`sa_api_room` `a` join `sa_api_bed` `b`) join `sa_api_filerecorded` `c`) join `number_inv` `d` on(((`a`.`id` = `b`.`room_id`) and (`b`.`id` = `c`.`bed_id`) and (`c`.`id` = `d`.`record_id`))));
CREATE ALGORITHM=UNDEFINED DEFINER=`sa_server`@`localhost` SQL SECURITY DEFINER VIEW `view_number_mrt` AS select `a`.`name` AS `room_name`,`b`.`name` AS `bed_name`,`c`.`file_basename` AS `file_basename`,`d`.`id` AS `id`,DATE_ADD(`d`.`dt`, INTERVAL 9 HOUR) AS `dt`,`d`.`ARTF` AS `ARTF`,`d`.`EMG` AS `EMG`,`d`.`PSI` AS `PSI`,`d`.`SEFL` AS `SEFL`,`d`.`SEFR` AS `SEFR`,`d`.`SR` AS `SR` from (((`sa_api_room` `a` join `sa_api_bed` `b`) join `sa_api_filerecorded` `c`) join `number_mrt` `d` on(((`a`.`id` = `b`.`room_id`) and (`b`.`id` = `c`.`bed_id`) and (`c`.`id` = `d`.`record_id`))));
CREATE ALGORITHM=UNDEFINED DEFINER=`sa_server`@`localhost` SQL SECURITY DEFINER VIEW `view_number_piv` AS select `a`.`name` AS `room_name`,`b`.`name` AS `bed_name`,`c`.`file_basename` AS `file_basename`,`d`.`id` AS `id`,DATE_ADD(`d`.`dt`, INTERVAL 9 HOUR) AS `dt`,`d`.`ABP_SBP` AS `ABP_SBP`,`d`.`ABP_DBP` AS `ABP_DBP`,`d`.`ABP_MBP` AS `ABP_MBP`,`d`.`AOP_SBP` AS `AOP_SBP`,`d`.`AOP_DBP` AS `AOP_DBP`,`d`.`AOP_MBP` AS `AOP_MBP`,`d`.`AWAY_RR` AS `AWAY_RR`,`d`.`AWAY_TOT` AS `AWAY_TOT`,`d`.`AWAY_O2_INSP` AS `AWAY_O2_INSP`,`d`.`BIS_BIS` AS `BIS_BIS`,`d`.`BIS_EMG` AS `BIS_EMG`,`d`.`BIS_SQI` AS `BIS_SQI`,`d`.`BIS_SEF` AS `BIS_SEF`,`d`.`BIS_SR` AS `BIS_SR`,`d`.`BT_BLD` AS `BT_BLD`,`d`.`BT_NASOPH` AS `BT_NASOPH`,`d`.`BT_RECT` AS `BT_RECT`,`d`.`BT_SKIN` AS `BT_SKIN`,`d`.`CI` AS `CI`,`d`.`CO` AS `CO`,`d`.`CO2_ET` AS `CO2_ET`,`d`.`CO2_INSP_MIN` AS `CO2_INSP_MIN`,`d`.`CPP` AS `CPP`,`d`.`CVP_SBP` AS `CVP_SBP`,`d`.`CVP_DBP` AS `CVP_DBP`,`d`.`CVP_MBP` AS `CVP_MBP`,`d`.`DESFL_INSP` AS `DESFL_INSP`,`d`.`DESFL_ET` AS `DESFL_ET`,`d`.`ECG_HR` AS `ECG_HR`,`d`.`ECG_ST_I` AS `ECG_ST_I`,`d`.`ECG_ST_II` AS `ECG_ST_II`,`d`.`ECG_ST_III` AS `ECG_ST_III`,`d`.`ECG_ST_MCL` AS `ECG_ST_MCL`,`d`.`ECG_ST_V` AS `ECG_ST_V`,`d`.`ECG_ST_AVF` AS `ECG_ST_AVF`,`d`.`ECG_ST_AVL` AS `ECG_ST_AVL`,`d`.`ECG_ST_AVR` AS `ECG_ST_AVR`,`d`.`ECG_QT_GL` AS `ECG_QT_GL`,`d`.`ECG_QT_HR` AS `ECG_QT_HR`,`d`.`ECG_QTc` AS `ECG_QTc`,`d`.`ECG_QTc_DELTA` AS `ECG_QTc_DELTA`,`d`.`ECG_VPC_CNT` AS `ECG_VPC_CNT`,`d`.`ENFL_ET` AS `ENFL_ET`,`d`.`ENFL_INSP` AS `ENFL_INSP`,`d`.`HAL_ET` AS `HAL_ET`,`d`.`HAL_INSP` AS `HAL_INSP`,`d`.`HR` AS `HR`,`d`.`ICP_MBP` AS `ICP_MBP`,`d`.`ISOFL_ET` AS `ISOFL_ET`,`d`.`ISOFL_INSP` AS `ISOFL_INSP`,`d`.`LAP_MBP` AS `LAP_MBP`,`d`.`LAP_DBP` AS `LAP_DBP`,`d`.`LAP_SBP` AS `LAP_SBP`,`d`.`N2O_ET` AS `N2O_ET`,`d`.`N2O_INSP` AS `N2O_INSP`,`d`.`NIBP_HR` AS `NIBP_HR`,`d`.`NIBP_SBP` AS `NIBP_SBP`,`d`.`NIBP_DBP` AS `NIBP_DBP`,`d`.`NIBP_MBP` AS `NIBP_MBP`,`d`.`O2_ET` AS `O2_ET`,`d`.`O2_INSP` AS `O2_INSP`,`d`.`PAP_SBP` AS `PAP_SBP`,`d`.`PAP_DBP` AS `PAP_DBP`,`d`.`PAP_MBP` AS `PAP_MBP`,`d`.`PLETH_PERF_REL` AS `PLETH_PERF_REL`,`d`.`PLETH_HR` AS `PLETH_HR`,`d`.`PLETH_SAT_O2` AS `PLETH_SAT_O2`,`d`.`PLAT_TIME` AS `PLAT_TIME`,`d`.`PPV` AS `PPV`,`d`.`PTC_CNT` AS `PTC_CNT`,`d`.`RAP_SBP` AS `RAP_SBP`,`d`.`RAP_DBP` AS `RAP_DBP`,`d`.`RAP_MBP` AS `RAP_MBP`,`d`.`RISE_TIME` AS `RISE_TIME`,`d`.`RR` AS `RR`,`d`.`REF` AS `REF`,`d`.`SET_SPEEP` AS `SET_SPEEP`,`d`.`SET_INSP_TIME` AS `SET_INSP_TIME`,`d`.`SEVOFL_ET` AS `SEVOFL_ET`,`d`.`SEVOFL_INSP` AS `SEVOFL_INSP`,`d`.`SI` AS `SI`,`d`.`SV` AS `SV`,`d`.`SVV` AS `SVV`,`d`.`TEMP` AS `TEMP`,`d`.`TEMP_ESOPH` AS `TEMP_ESOPH`,`d`.`TV_IN` AS `TV_IN`,`d`.`TOF_RATIO` AS `TOF_RATIO`,`d`.`TOF_CNT` AS `TOF_CNT`,`d`.`TOF_1` AS `TOF_1`,`d`.`TOF_2` AS `TOF_2`,`d`.`TOF_3` AS `TOF_3`,`d`.`TOF_4` AS `TOF_4`,`d`.`UA_MBP` AS `UA_MBP`,`d`.`UA_DBP` AS `UA_DBP`,`d`.`UA_SBP` AS `UA_SBP` from (((`sa_api_room` `a` join `sa_api_bed` `b`) join `sa_api_filerecorded` `c`) join `number_piv` `d` on(((`a`.`id` = `b`.`room_id`) and (`b`.`id` = `c`.`bed_id`) and (`c`.`id` = `d`.`record_id`))));
CREATE ALGORITHM=UNDEFINED DEFINER=`sa_server`@`localhost` SQL SECURITY DEFINER VIEW `view_number_prm` AS select `a`.`name` AS `room_name`,`b`.`name` AS `bed_name`,`c`.`file_basename` AS `file_basename`,`d`.`id` AS `id`,DATE_ADD(`d`.`dt`, INTERVAL 9 HOUR) AS `dt`,`d`.`ART_MBP` AS `ART_MBP`,`d`.`CI` AS `CI`,`d`.`CO` AS `CO`,`d`.`COMPLIANCE` AS `COMPLIANCE`,`d`.`CONSUMPTION_AIR` AS `CONSUMPTION_AIR`,`d`.`CONSUMPTION_DES` AS `CONSUMPTION_DES`,`d`.`CONSUMPTION_ENF` AS `CONSUMPTION_ENF`,`d`.`CONSUMPTION_HALO` AS `CONSUMPTION_HALO`,`d`.`CONSUMPTION_ISO` AS `CONSUMPTION_ISO`,`d`.`CONSUMPTION_N2O` AS `CONSUMPTION_N2O`,`d`.`CONSUMPTION_O2` AS `CONSUMPTION_O2`,`d`.`CONSUMPTION_SEVO` AS `CONSUMPTION_SEVO`,`d`.`ETCO2` AS `ETCO2`,`d`.`ETCO2_KPA` AS `ETCO2_KPA`,`d`.`ETCO2_PERCENT` AS `ETCO2_PERCENT`,`d`.`EXP_DES` AS `EXP_DES`,`d`.`EXP_ENF` AS `EXP_ENF`,`d`.`EXP_HALO` AS `EXP_HALO`,`d`.`EXP_ISO` AS `EXP_ISO`,`d`.`EXP_SEVO` AS `EXP_SEVO`,`d`.`FEN2O` AS `FEN2O`,`d`.`FEO2` AS `FEO2`,`d`.`FIN2O` AS `FIN2O`,`d`.`FIO2` AS `FIO2`,`d`.`FLOW_AIR` AS `FLOW_AIR`,`d`.`FLOW_N2O` AS `FLOW_N2O`,`d`.`FLOW_O2` AS `FLOW_O2`,`d`.`GAS2_EXPIRED` AS `GAS2_EXPIRED`,`d`.`INCO2` AS `INCO2`,`d`.`INCO2_KPA` AS `INCO2_KPA`,`d`.`INCO2_PERCENT` AS `INCO2_PERCENT`,`d`.`INSP_DES` AS `INSP_DES`,`d`.`INSP_ENF` AS `INSP_ENF`,`d`.`INSP_HALO` AS `INSP_HALO`,`d`.`INSP_ISO` AS `INSP_ISO`,`d`.`INSP_SEVO` AS `INSP_SEVO`,`d`.`MAC` AS `MAC`,`d`.`MAWP_MBAR` AS `MAWP_MBAR`,`d`.`MV` AS `MV`,`d`.`MV_SPONT` AS `MV_SPONT`,`d`.`NIBP_DBP` AS `NIBP_DBP`,`d`.`NIBP_MBP` AS `NIBP_MBP`,`d`.`NIBP_SBP` AS `NIBP_SBP`,`d`.`PAMB_MBAR` AS `PAMB_MBAR`,`d`.`PEEP_MBAR` AS `PEEP_MBAR`,`d`.`PIP_MBAR` AS `PIP_MBAR`,`d`.`PLETH_SPO2` AS `PLETH_SPO2`,`d`.`PPLAT_MBAR` AS `PPLAT_MBAR`,`d`.`RESISTANCE` AS `RESISTANCE`,`d`.`RR_CO2` AS `RR_CO2`,`d`.`RR_MANDATORY` AS `RR_MANDATORY`,`d`.`RR_SPONT` AS `RR_SPONT`,`d`.`RR_VF` AS `RR_VF`,`d`.`RVSWI` AS `RVSWI`,`d`.`SET_EXP_AGENT` AS `SET_EXP_AGENT`,`d`.`SET_EXP_ENF` AS `SET_EXP_ENF`,`d`.`SET_EXP_HALO` AS `SET_EXP_HALO`,`d`.`SET_EXP_SEVO` AS `SET_EXP_SEVO`,`d`.`SET_EXP_TM` AS `SET_EXP_TM`,`d`.`SET_FIO2` AS `SET_FIO2`,`d`.`SET_FLOW_TRIG` AS `SET_FLOW_TRIG`,`d`.`SET_FRESH_AGENT` AS `SET_FRESH_AGENT`,`d`.`SET_FRESH_DES` AS `SET_FRESH_DES`,`d`.`SET_FRESH_ENF` AS `SET_FRESH_ENF`,`d`.`SET_FRESH_FLOW` AS `SET_FRESH_FLOW`,`d`.`SET_FRESH_HALO` AS `SET_FRESH_HALO`,`d`.`SET_FRESH_ISO` AS `SET_FRESH_ISO`,`d`.`SET_FRESH_O2` AS `SET_FRESH_O2`,`d`.`SET_IE_E` AS `SET_IE_E`,`d`.`SET_IE_I` AS `SET_IE_I`,`d`.`SET_INSP_PAUSE` AS `SET_INSP_PAUSE`,`d`.`SET_INSP_PRES` AS `SET_INSP_PRES`,`d`.`SET_INSP_TM` AS `SET_INSP_TM`,`d`.`SET_INTER_PEEP` AS `SET_INTER_PEEP`,`d`.`SET_PEEP` AS `SET_PEEP`,`d`.`SET_PIP` AS `SET_PIP`,`d`.`SET_RR_IPPV` AS `SET_RR_IPPV`,`d`.`SET_SUPP_PRES` AS `SET_SUPP_PRES`,`d`.`SET_TV` AS `SET_TV`,`d`.`SET_TV_L` AS `SET_TV_L`,`d`.`ST_AVF` AS `ST_AVF`,`d`.`ST_AVR` AS `ST_AVR`,`d`.`ST_I` AS `ST_I`,`d`.`ST_II` AS `ST_II`,`d`.`ST_III` AS `ST_III`,`d`.`ST_V5` AS `ST_V5`,`d`.`ST_VPLUS` AS `ST_VPLUS`,`d`.`SUPPLY_PRESSURE_O2` AS `SUPPLY_PRESSURE_O2`,`d`.`SV` AS `SV`,`d`.`SVR` AS `SVR`,`d`.`TV` AS `TV`,`d`.`TV_MANDATORY` AS `TV_MANDATORY`,`d`.`VENT_LEAK` AS `VENT_LEAK` from (((`sa_api_room` `a` join `sa_api_bed` `b`) join `sa_api_filerecorded` `c`) join `number_prm` `d` on(((`a`.`id` = `b`.`room_id`) and (`b`.`id` = `c`.`bed_id`) and (`c`.`id` = `d`.`record_id`))));
CREATE ALGORITHM=UNDEFINED DEFINER=`sa_server`@`localhost` SQL SECURITY DEFINER VIEW `view_number_vig` AS select `a`.`name` AS `room_name`,`b`.`name` AS `bed_name`,`c`.`file_basename` AS `file_basename`,`d`.`id` AS `id`,DATE_ADD(`d`.`dt`, INTERVAL 9 HOUR) AS `dt`,`d`.`ART_MBP` AS `ART_MBP`,`d`.`BT_PA` AS `BT_PA`,`d`.`CI` AS `CI`,`d`.`CI_STAT` AS `CI_STAT`,`d`.`CO` AS `CO`,`d`.`CO_STAT` AS `CO_STAT`,`d`.`CVP` AS `CVP`,`d`.`DO2` AS `DO2`,`d`.`EDV` AS `EDV`,`d`.`EDVI` AS `EDVI`,`d`.`EDVI_STAT` AS `EDVI_STAT`,`d`.`EDV_STAT` AS `EDV_STAT`,`d`.`ESV` AS `ESV`,`d`.`ESVI` AS `ESVI`,`d`.`HR_AVG` AS `HR_AVG`,`d`.`ICI` AS `ICI`,`d`.`ICI_AVG` AS `ICI_AVG`,`d`.`ICO_AVG` AS `ICO_AVG`,`d`.`O2EI` AS `O2EI`,`d`.`RVEF` AS `RVEF`,`d`.`RVEF_STAT` AS `RVEF_STAT`,`d`.`SAO2` AS `SAO2`,`d`.`SCVO2` AS `SCVO2`,`d`.`SNR` AS `SNR`,`d`.`SQI` AS `SQI`,`d`.`SV` AS `SV`,`d`.`SVI` AS `SVI`,`d`.`SVI_STAT` AS `SVI_STAT`,`d`.`SVO2` AS `SVO2`,`d`.`SVR` AS `SVR`,`d`.`SVRI` AS `SVRI`,`d`.`SVV` AS `SVV`,`d`.`SV_STAT` AS `SV_STAT`,`d`.`VO2` AS `VO2` from (((`sa_api_room` `a` join `sa_api_bed` `b`) join `sa_api_filerecorded` `c`) join `number_vig` `d` on(((`a`.`id` = `b`.`room_id`) and (`b`.`id` = `c`.`bed_id`) and (`c`.`id` = `d`.`record_id`))));
