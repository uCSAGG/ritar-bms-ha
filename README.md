# ritar-bms-ha
<b>Homeassitant Addon for Ritar BAT-5KWH-51.2V BMS</b></br>

<b>Stable release<b>, based on standalone web service https://github.com/mamontuka/ritar-bms </br>

Instalation : </br>
1 - Add this repository to addons (three dots) - https://github.com/mamontuka/ritar-bms-ha </br>
2 - Install this addon </br>
3 - In addon setings choose RS485 gate IP, port, and how much battery you have (at now supported 1 or 2) </br>
4 - Take examples below, ajust for self </br>

UPDATE 1.1 - added cells temperature sensors 1-4 for batteries 1-2, example templates updated</br>
UPDATE 1.2 - added MOS and Environment temperature sensors, major bugfixes, stability improvements, reading timeout set over config, example templates updated with new sensors. </br>
UPDATE 1.3 - added Current charge/discharge Ampers sensor, example templates updated with new sensor. </br>
UPDATE 1.4 - added WATTmeter charge/discharge power sensor, configurable RS485 connection timeout, configurable queries delay (usualy not need to be ajusted, but let it be), reworked voltage and SOC sensors API annoncement,  example templates updated.

Homeassitant configuration examples : https://github.com/mamontuka/ritar-bms/tree/main/standalone_web_service/ritar-bms/web_ui/examples </br>

