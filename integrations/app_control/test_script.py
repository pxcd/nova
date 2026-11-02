import asyncio,yaml
from homeassistant.core import HomeAssistant,Context
from homeassistant.helpers.script import Script
from homeassistant.helpers import config_validation as cv
async def main():
 hass=HomeAssistant('/tmp/nova-quit-check');raw=yaml.safe_load(open('/config/scripts.yaml'))['force_quit_tv_app']['sequence'];calls=[];outcome='OK'
 async def capture(call):
  calls.append(dict(call.data));hass.states.async_set('media_player.android_tv_10_0_0_174','idle',{'adb_response':'NOVA_QUIT_'+outcome+'_'+(call.context.id if outcome!='STALE' else 'previous-context')})
 hass.services.async_register('androidtv','adb_command',capture);script=Script(hass,cv.SCRIPT_SCHEMA(raw),'Quit test','script')
 async def run(app):
  calls.clear();return(await script.async_run({'app':app},Context())).service_response
 for app,pkg in {'Netflix':'com.netflix.ninja','HBO Max':'com.wbd.stream','Prime Video':'com.amazon.amazonvideo.livingroom','Apple TV':'com.apple.atve.sony.appletv','Kodi':'org.xbmc.kodi'}.items():
  r=await run(app);assert r['status']=='force_quit_confirmed' and r['force_quit_verified'] is True;assert calls[0]['command'].startswith("am force-stop '"+pkg+"'")
 for app in ['Settings',"Netflix'; reboot",'com.netflix.ninja']:
  r=await run(app);assert r['status']=='unsupported_app' and not calls
 for value in ['PENDING','STALE','ERROR']:
  outcome=value;r=await run('Prime Video');assert r['status']=='failed' and r['force_quit_verified'] is False
 print('PASS five allowlisted apps, exact package mapping, injection/unknown app rejection, and pending/stale/error failures. Services mocked.')
asyncio.run(main())
