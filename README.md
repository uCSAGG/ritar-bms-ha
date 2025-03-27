# ritar-bms-ha
<b>Homeassitant Addon for Ritar BAT-5KWH-51.2V BMS</b></br>

<b>Stable release<b>, based on standalone web service https://github.com/mamontuka/ritar-bms </br>

Instalation : </br>
1 - Add this repository to addons (three dots) - https://github.com/mamontuka/ritar-bms-ha </br>
2 - Install this addon </br>
3 - In addon setings choose RS485 gate IP, port, and how much battery you have (at now supported 1 or 2) </br>
4 - Take examples below, ajust for self </br>

UPDATE 1.1 - added cells temperature sensors 1-4 for batteries 1-2, example templates updated</br>

Homeassitant configuration examples : https://github.com/mamontuka/ritar-bms/tree/main/standalone_web_service/ritar-bms/web_ui/examples </br>
With this addon, in configuration.yaml example, 192.168.5.3 (remote standalone service example IP) must be changed on "localhost" (without quotes), because this addon works localy in homeassistant in native mode
