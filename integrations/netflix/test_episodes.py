import asyncio,copy,json,yaml
from pathlib import Path
from homeassistant.core import HomeAssistant,Context,SupportsResponse
from homeassistant.helpers.script import Script
from homeassistant.helpers import config_validation as cv

def no_delays(v):
 if isinstance(v,list):return [no_delays(x) for x in v if not(isinstance(x,dict) and 'delay' in x)]
 if isinstance(v,dict):return {k:no_delays(x) for k,x in v.items()}
 return v
async def main():
 hass=HomeAssistant('/tmp/nova-episode-check');raw=yaml.safe_load(Path('/config/scripts.yaml').read_text())['play_netflix_title'];fixture={'title':'Brooklyn Nine-Nine','showType':'series','overview':'x'*300000,'streamingOptions':{'ph':[{'service':{'id':'netflix'},'type':'subscription','link':'https://www.netflix.com/title/70281562'}]},'seasons':[{'title':'Season 1','episodes':[{'title':'Pilot','streamingOptions':{'ph':[{'service':{'id':'netflix'},'type':'subscription','link':'https://www.netflix.com/watch/80004161'}]}},{'title':'The Tagger','streamingOptions':{'ph':[{'service':{'id':'netflix'},'type':'subscription','link':'https://www.netflix.com/watch/80004162'}]}}]},{'title':'Season 2','episodes':[]}]};content=[copy.deepcopy(fixture)];calls=[];lookups=[]
 async def lookup(call):lookups.append(dict(call.data));return {'status':200,'content':content}
 async def capture(call):calls.append((call.domain,call.service,dict(call.data)))
 async def restart(call):calls.append(('script','restart',{}));return {'status':'restart_requested','message':'Restart selected.'}
 hass.services.async_register('rest_command','netflix_title_search',lookup,supports_response=SupportsResponse.ONLY)
 for domain,name in [('remote','send_command'),('media_player','play_media')]:hass.services.async_register(domain,name,capture)
 hass.services.async_register('script','netflix_restart_from_playback',restart,supports_response=SupportsResponse.ONLY)
 script=Script(hass,cv.SCRIPT_SCHEMA(no_delays(raw['sequence'])),'Episode check','script')
 async def run(**args):calls.clear();lookups.clear();return(await script.async_run({'query':'Brooklyn Nine-Nine',**args},Context())).service_response
 r=await run();assert r['status']=='title_link_sent';assert '/title/' in calls[-1][2]['media_content_id'];assert lookups[0]['series_granularity']=='show'
 r=await run(season=1,episode=2);assert r['season']==1 and r['episode']==2 and r['episode_title']=='The Tagger';assert calls[-1][2]['media_content_id']=='https://www.netflix.com/watch/80004162?source=30';assert lookups[0]['series_granularity']=='episode'
 r=await run(season=1,episode=2,from_start=True);assert r['status']=='restart_requested' and calls[-1][:2]==('script','restart')
 for args,status in [({'season':1},'needs_episode'),({'episode':2},'needs_episode'),({'season':True,'episode':1},'invalid_episode'),({'season':1,'episode':1.5},'invalid_episode'),({'season':'1','episode':2},'invalid_episode'),({'season':0,'episode':1},'invalid_episode')]:
  r=await run(**args);assert r['status']==status,(args,r);assert not calls and not lookups
 r=await run(season=99,episode=1);assert r['status']=='unavailable' and not calls
 r=await run(season=1,episode=999);assert r['status']=='unavailable' and not calls
 content[0]['seasons'].reverse();r=await run(season=1,episode=2);assert r['episode_title']=='The Tagger'
 season=next(s for s in content[0]['seasons'] if s['title']=='Season 1');season['episodes'][1]['streamingOptions']={};r=await run(season=1,episode=2);assert r['status']=='unavailable' and not calls
 content[0]['showType']='movie';r=await run(season=1,episode=2);assert r['status']=='invalid_episode' and not calls
 print('PASS ordinary resume preserved; S1E2 resolves episode ID; explicit restart preserved; missing/invalid inputs, absent seasons/episodes/provider links and movies blocked without TV commands; season labels tolerate reordered arrays. All TV services mocked.')
asyncio.run(main())
