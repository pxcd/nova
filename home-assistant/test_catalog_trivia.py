import asyncio,yaml
from pathlib import Path
from homeassistant.core import HomeAssistant
from homeassistant.helpers.template import Template
async def main():
 hass=HomeAssistant('/tmp/nova-trivia-check');scripts=yaml.safe_load(Path('/config/scripts.yaml').read_text());templates=[]
 def visit(v):
  if isinstance(v,dict):
   if 'trivia_fact' in v:templates.append(v['trivia_fact'])
   for c in v.values():visit(c)
  elif isinstance(v,list):
   for c in v:visit(c)
 for name in ['play_netflix_title','play_hbo_title','play_prime_video_title','play_apple_tv_title']:visit(scripts[name])
 assert len(templates)==5
 movie={'title':'White Chicks','showType':'movie','releaseYear':2004,'directors':['Keenen Ivory Wayans'],'cast':['Shawn Wayans','Marlon Wayans'],'overview':'SPOILER_SENTINEL'}
 allowed={'It was released in 2004.','Directed by Keenen Ivory Wayans.','The cast includes Shawn Wayans.','The cast includes Marlon Wayans.'}
 for source in templates:
  t=Template(source,hass);t.ensure_valid()
  for _ in range(20):assert t.async_render({'matches':[movie]}) in allowed
  assert t.async_render({'matches':[{'title':'Empty'}]})==''
  assert t.async_render({'matches':[{'showType':'series','firstAirYear':1997}]})=='It premiered in 1997.'
 print('PASS all five streaming result paths: supplied credits/year only; no overview; absent metadata skips trivia; series uses premiere year. No TV actions.')
asyncio.run(main())
