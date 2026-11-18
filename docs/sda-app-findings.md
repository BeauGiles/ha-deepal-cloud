# What the official app shows about the SDA (E07) interface

This page lists **names** found in the official Deepal app (iOS, overseas build 1.12.0) by reading its string table and its bundled web mini-apps. It is meant as a starting point for anyone working on the E07 and other SDA cars, including other integrations. Reuse it freely.

## Read this first

- **Names only.** No request bodies, parameter values, response shapes, keys or tokens were recovered. Nothing was run and no traffic was captured.
- **Unverified.** A name appearing in the app does not mean your car or account uses it, that it works for a shared secondary account, or what its values mean. Units, scaling and enums are unknown.
- **Not in this repo's code.** Nothing on this page is used by the integration, except where noted. The diagnostics download probes a few of these endpoints read-only so real responses can be collected (see "Where this is going").
- Names in the Android build of the same version are not visible, because that build is packed.

## What is confirmed

| Item | Status |
|---|---|
| `car-ctrl/getCarConditionByCarId` returns the E07 condition | Used by this integration; works on a real E07 |
| `Cnr_ReWakeup` (service `TxWakeup`) wakes the car | Live-verified by Sunek0/ha-deepal-alternative on an S05 only |
| `Et_IT001` carries lock states | Reported by Sunek0's SDA probe |
| Everything else below | Name seen in the app only |

## How remote control appears to work

The app's remote-control module connects to an MQTT broker whose settings come from `car-ctrl/get-mqtt-server-config`, with a token from `vot-auth/api/token/getAuthTokenByUserId`. Its message header has the fields `requestID`, `productKey`, `serviceKey`, `methodType`, `encryptFlag` and `timestamp`, and separate payload types for actions, errors and events (condition, location, monitor, sentinel, OTA). Commands are the `Cnr_*` names below; events are `Et_*`.

**Still unknown:** the exact frame, the parameters of each command and the encryption key handling. Sunek0's capture kit notes that command codes travel AES-encrypted inside `sers`. A real capture of one command is the missing piece.

## Gateway paths (48)

All sit under the gateway prefix `/app-apigw/`. Login, PIN, digital-key, key-sharing and log-upload endpoints are deliberately left out: they are of no use to a Home Assistant integration and are better not listed.


**car-info-api**

- `/app-apigw/car-info-api/api/v1/sda-app/car/my-car-list`
- `/app-apigw/car-info-api/api/v1/sda-app/car/my-device-list`
- `/app-apigw/car-info-api/api/v1/sda-app/ota/get-progress`
- `/app-apigw/car-info-api/api/v1/sda-app/ota/get-task`
- `/app-apigw/car-info-api/api/v1/sda-app/ota/get-upgrade-history`
- `/app-apigw/car-info-api/api/v1/sda-app/vin-charge/add`
- `/app-apigw/car-info-api/api/v1/sda-app/vin-charge/list`
- `/app-apigw/car-info-api/api/v1/sda-app/vin-charge/status`

**client-common-api**

- `/app-apigw/client-common-api/api/v1/sda-app/event-tracking/upload`
- `/app-apigw/client-common-api/api/v1/sda-app/message/send-auth-code`

**content-center-api**

- `/app-apigw/content-center-api/api/v1/sda-app/res/common/list`
- `/app-apigw/content-center-api/api/v1/sda-app/res/ota/list`

**data-api**

- `/app-apigw/data-api/api/energy-center-doris/energy-rank`
- `/app-apigw/data-api/api/energy-center-doris/energy_stat`
- `/app-apigw/data-api/api/energy-center-doris/one-month-energy-info`
- `/app-apigw/data-api/api/energy-center-doris/one-year-energy-info`
- `/app-apigw/data-api/api/vin-milg-history/energy-curve`
- `/app-apigw/data-api/api/vin-milg-history/milg-energy-info`

**dt-m3d-app**

- `/app-apigw/dt-m3d-app/api/v1/app/model-3d/create-car-instance/`

**dt-pt-app**

- `/app-apigw/dt-pt-app/api/v2/app/script/my/info/list`

**mservice**

- `/app-apigw/mservice/api/v3/weather/location/get-detail`

**sda-app-control**

- `/app-apigw/sda-app-control/api/v1/sda-app/app-func/get-function`
- `/app-apigw/sda-app-control/api/v1/sda-app/car-ctrl/get-mqtt-server-config`
- `/app-apigw/sda-app-control/api/v1/sda-app/car-ctrl/getCarConditionByCarId`
- `/app-apigw/sda-app-control/api/v1/sda-app/car-ctrl/getCmdLogByEventTypeCarId`
- `/app-apigw/sda-app-control/api/v1/sda-app/car-ctrl/rapid-func`
- `/app-apigw/sda-app-control/api/v1/sda-app/car-ctrl/send-to-car`
- `/app-apigw/sda-app-control/api/v1/sda-app/car-event/last`

**store-sda-api**

- `/app-apigw/store-sda-api/api/v2/mobile-data/total`
- `/app-apigw/store-sda-api/api/v2/top-rights/top-rights-info`

**user-info-api**

- `/app-apigw/user-info-api/api/v1/optional-fund/summary`
- `/app-apigw/user-info-api/api/v1/sda-app/electronic-fence/add`
- `/app-apigw/user-info-api/api/v1/sda-app/electronic-fence/delete`
- `/app-apigw/user-info-api/api/v1/sda-app/electronic-fence/query`
- `/app-apigw/user-info-api/api/v1/sda-app/electronic-fence/update`
- `/app-apigw/user-info-api/api/v1/sda-app/individuation/batch-get`
- `/app-apigw/user-info-api/api/v1/sda-app/individuation/batch-update`
- `/app-apigw/user-info-api/api/v1/sda-app/individuation/get`
- `/app-apigw/user-info-api/api/v1/sda-app/individuation/update`
- `/app-apigw/user-info-api/api/v1/sda-app/personal-info/basic-information`
- `/app-apigw/user-info-api/api/v1/sda-app/personal-info/basic_information`
- `/app-apigw/user-info-api/api/v1/sda-app/user-default-car/set`
- `/app-apigw/user-info-api/api/v1/sda-hu/user-address-info/get`

**vot-api-server**

- `/app-apigw/vot-api-server/api/product/getProtocolTypeByCarId`
- `/app-apigw/vot-api-server/strategy/list`

**vot-auth**

- `/app-apigw/vot-auth/api/token/getAuthTokenByUserId`

**vot-connect-conf-center**

- `/app-apigw/vot-connect-conf-center/api/device/appGetCarConfFunc`

**vot-vrtm-car-condition**

- `/app-apigw/vot-vrtm-car-condition/api/car/condition/latest/get`

## Command names, `Cnr_*` (105)


**Doors, trunk, windows, roof, mirrors**

`Cnr_AutoWindUnlock`, `Cnr_TailGateDrv_ReqSt`, `Cnr_AutoWindLongPress`, `Cnr_TxPartWinCtrl`, `Cnr_FrntWindHeat`, `Cnr_TxMirrElecHeat`, `Cnr_ACAutoWind`, `Cnr_AllDoorSet`, `Cnr_FLDoorSet`, `Cnr_FRDoorSet`, `Cnr_RLDoorSet`, `Cnr_RRDoorSet`, `Cnr_TxTrunkALL`, `Cnr_SunRoofCtrl`, `Cnr_TxSunShade`, `Cnr_WinAllCtrl`


**Climate, air and fragrance**

`Cnr_ACMaxHeatSet`, `Cnr_AirCleanSwitch`, `Cnr_RR_ACIonizer`, `Cnr_Fr_ACAutoMod`, `Cnr_Rr_ACAutoMod`, `Cnr_CustomFragranceSet`, `Cnr_AFUContentleve`, `Cnr_FrACDefAdjSet`, `Cnr_APAControleReq`, `Cnr_MorningVentnSet`, `Cnr_AfternoonVentnSet`, `Cnr_EveningVentnSet`, `Cnr_APP_RMACntrlcomnd`, `Cnr_ACMaxAC`, `Cnr_AirFctSt`, `Cnr_CycleSwitch`, `Cnr_Fr_ACAuto`, `Cnr_Fr_ACOffReq`, `Cnr_Rr_ACOffReq`, `Cnr_DrACTemp`, `Cnr_PaACTemp`, `Cnr_RrACTemp`, `Cnr_SyncSwitch`, `Cnr_HotColdMod`, `Cnr_FrACBlowMod`, `Cnr_RrACBlowMod`, `Cnr_ACCircMode`, `Cnr_AirOut`, `Cnr_FrACBlowLvl`, `Cnr_RrACBlowLvl`, `Cnr_ACDeicing`, `Cnr_AFUSt`, `Cnr_AFUchannel`, `Cnr_ACAutoDef`, `Cnr_VentnModSet`, `Cnr_DrACCnr_PaACCnr_RrACMQTTADScoreCmd`


**Seats and steering wheel**

`Cnr_RearSeatHeat`, `Cnr_RearLeSeatHeat`, `Cnr_RearRiSeatHeat`, `Cnr_RearSeatVent`, `Cnr_RearLeSeatVent`, `Cnr_RearRiSeatVent`, `Cnr_SeatCtrlSpaceMax`, `Cnr_FronSeatCtrl`, `Cnr_TxSteeringHeat`, `Cnr_DrSeatHeat`, `Cnr_PsgSeatHeat`, `Cnr_DrSeatVent`, `Cnr_PsgSeatVent`


**Charging and battery**

`Cnr_SocChrgTarSet`, `Cnr_DchaSocLimitSet`, `Cnr_AcChrgILimtet`, `Cnr_AcChrgILimtet_wrapper`, `Cnr_RR_AcChrgLck`, `Cnr_VehChrgUnlckSet`, `Cnr_ChrgCbnCtrl`


**Security, sentry, camp and monitoring**

`Cnr_VideoMonitorPreCheck`, `Cnr_VideoMonitorSet`, `Cnr_CurPlayMusicMonitorCtrl`, `Cnr_ActSenMoInfoSet`, `Cnr_ActSenMoSwitSet`, `Cnr_ActSenWarningSet`, `Cnr_ActCampRangeSet`, `Cnr_ActCampWarningSet`, `Cnr_ActCampSwotSet`, `Cnr_APAParkVideoMonitor`, `Cnr_GuardModePicture`, `Cnr_StolenBack`


**Parking assist**

`Cnr_APAFunctionReq`, `Cnr_ScreenCoordinate`


**Media**

`Cnr_CurPlayMusic`, `Cnr_CurMediaVolumeSt`, `Cnr_CurPlayMode`, `Cnr_PlaySong`


**Wake, find car, lights, install, other**

`Cnr_*`, `Cnr_ReWakeup`, `Cnr_RemtCtrlClsTime`, `Cnr_RemoteInstall`, `Cnr_SoftSwtichSetTail`, `Cnr_Sys_RKESeekCar`, `Cnr_HUset_ADScoreSet`, `Cnr_RR_ObjDrv`, `Cnr_AllAc`, `Cnr_AllAcON`, `Cnr_AllAcOff`, `Cnr_DomeLiCtrl`, `Cnr_PredSet`, `Cnr_RemPwrUpSet`, `Cnr_ReWakeup`


## Event names, `Et_*` (35)

`Et_*`, `Et_ContiChangedAwaredCond`, `Et_ContiPeriodAwaredCond`, `ET_SMART_DEVICE_UPDATE`, `Et_ParkingLotNumber`, `Et_NetworkStatusRlt`, `Et_VideoMonitorCheckRlt`, `Et_ VideoMonitorRlt`, `Et_StolenBackRlt`, `Et_UserNotiConfir`, `Et_ActSenMoInfoSet`, `Et_GuardModePicture`, `Et_ScheduleService`, `Et_CarCond`, `Et_ActSenTrig`, `Et_ActSenFunEn`, `Et_CloudSetting`, `Et_CarData`, `Et_RI001`, `Et_IT088`, `Et_IT037`, `Et_IT087`, `Et_IT001`, `Et_CT002`, `Et_CT043`, `Et_RC003`, `Et_IT034`, `Et_IT036`, `Et_IT067`, `Et_IT065`, `Et_IT066`, `Et_IT093`, `Et_RI002`, `Et_CT005`, `Et_IT085`


## Signal names (75)

Cloud-style names (`Tpms…`, `Bcm…`, `Bcu…`, `Cdc…`, `Vcu…`, `VIU…`) in the same family as the E07 condition keys this integration already reads (`BcuSocDisp`, `VIUSocDisp`, `CdcTotMilg`, `DrvrDoorSts` …). Only seven appear anywhere in Sunek0/ha-deepal-alternative. **Which of these a real E07 returns is not known.** Tyre warnings, battery temperatures and energy-use figures are the interesting ones.

`BcmDrvrDoorLckSts`, `BcmFBLVehChrgSts`, `BcmFrntFogLmpSts`, `BcmPwrStsFb`, `BcuBattHeatActv`, `BcuBattI`, `BcuBattLowTempSts`, `BcuBattPlsHeagStsFb`, `BcuBattPlsHeatgGearReq`, `BcuBattTAvrg`, `BcuBattTMax`, `BcuBattTMin`, `BcuBattU`, `BcuBokgHeatTi`, `BcuChrgMod`, `BcuChrgSts`, `BcuChrgTiDisp`, `BcuChrgTiPred`, `BcuDchaIContnsMax`, `BcuDchaPwrContnsMax`, `BcuDchaTiDisp`, `BcuDchaTiDispRlt`, `BcuPlsHeatTiRem`, `BcuThermRunawaySts`, `CdcAcChrgILimSet`, `CdcBattPlsHeatgSet`, `CdcDchaSocLimitSet`, `CdcTotMilg`, `TpmsLeFrntTirePWarn`, `TpmsLeReTirePWarn`, `TpmsRiFrntTirePWarn`, `TpmsRiReTirePWarn`, `TpmsSysFailrWarn`, `VCUPlsHeatgAllwdFlg`, `VIUChargeStatus`, `VIUSocDisp`, `VcuChrgAutoUnlckSetStsFb`, `VcuChrgLckInfo`, `VcuChrgPlugTDetdDispReq`, `VcuChrgStsLamp`, `VcuChrgTextDisp`, `VcuDchaSocLimitVal`, `VcuEvDrvResiMilg`, `VcuFulLimdDrvgDst`, `VcuGearPosn`, `VcuPlugConnectLamp`, `VcuResiMilg`, `VcuSysEgyFlow`, `VcuUnreleasedMilgInLowT`, `VcuVehAvrEgyCnsegIn50km`, `VcuVehAvrgEgyCnse`, `VcuVehAvrgEgyCnseDrivingCyc`, `VcuVehAvrgEgyCnseIn10km`, `VcuVehAvrgEgyCnseIn25km`, `VcuVehAvrgEgyCnseInTripA`, `VcuVehAvrgEgyCnseLongTime`, `VcuVehAvrgEgyCnselongTime`, `VcuVehAvrgResiMilgIn10km`, `VcuVehAvrgResiMilgIn25km`, `VcuVehAvrgResiMilgIn50km`, `VcuVehChrgAvrgEgyCnse`, `VcuVehChrgEgyCnse`, `VcuVehChrgStsGb`, `VcuVehDecrMilg`, `VcuVehEgyCnseDrivingCyc`, `VcuVehEgyCnseIn10km`, `VcuVehEgyCnseIn25km`, `VcuVehEgyCnseIn50km`, `VcuVehEgyCnseInTripA`, `VcuVehEgyCnseLongTime`, `VcuVehEgyCnseSelectCfm`, `VcuVehIncrMilg`, `VcuVehResiMilgIn10km`, `VcuVehResiMilgIn25km`, `VcuVehResiMilgIn50km`

## Where this is going

- The diagnostics download of an E07 already includes `endpoint_probes` (read-only calls to a few of the endpoints above) and the SDA Data sensor lists signals no entity reads yet. Real responses from owners are what turn names into sensors.
- Remote control needs one captured command per function. Do not send guessed commands to a car.

If you find a name here that is wrong, or confirm one, please open an issue.
