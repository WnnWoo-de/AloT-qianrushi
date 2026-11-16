(function(){
  const config=window.API_CONFIG;

  function trimSlash(value){return String(value||'').replace(/\/+$/,'');}
  function sameOriginAvailable(){return location.protocol==='http:' || location.protocol==='https:';}
  function hasApiEndpoint(){return Boolean(trimSlash(config.API_BASE_URL)) || sameOriginAvailable();}
  function hasWsEndpoint(){return Boolean(trimSlash(config.WS_BASE_URL)) || sameOriginAvailable();}
  function apiUrl(path){
    const suffix=String(path||'').startsWith('/')?path:'/'+path;
    const base=trimSlash(config.API_BASE_URL) || (sameOriginAvailable()?location.origin:'');
    return base+trimSlash(config.API_PREFIX)+suffix;
  }
  function wsUrl(path){
    const suffix=String(path||'').startsWith('/')?path:'/'+path;
    let base=trimSlash(config.WS_BASE_URL);
    if(!base && sameOriginAvailable()) base=(location.protocol==='https:'?'wss://':'ws://')+location.host;
    return base+suffix;
  }

  async function request(path,options={}){
    if(!hasApiEndpoint()) throw new Error('SERVICE_ENDPOINT_UNBOUND');
    const controller=new AbortController();
    const timer=setTimeout(()=>controller.abort(),config.REQUEST_TIMEOUT);
    try{
      const response=await fetch(apiUrl(path),{
        method:options.method||'GET',
        headers:Object.assign({'Content-Type':'application/json'},options.headers||{}),
        body:options.body===undefined?undefined:JSON.stringify(options.body),
        signal:controller.signal
      });
      if(!response.ok) throw new Error('HTTP_'+response.status);
      const payload=await response.json();
      if(payload&&typeof payload==='object'&&Object.prototype.hasOwnProperty.call(payload,'code')){
        if(payload.code!==0) throw new Error(payload.message||'BUSINESS_ERROR');
        return payload.data;
      }
      return payload;
    }finally{clearTimeout(timer);}
  }

  function connectMonitor(onMessage,onStateChange){
    if(!hasWsEndpoint()) return null;
    const socket=new WebSocket(wsUrl('/ws/monitor'));
    socket.addEventListener('open',()=>onStateChange&&onStateChange('open'));
    socket.addEventListener('close',()=>onStateChange&&onStateChange('closed'));
    socket.addEventListener('error',()=>onStateChange&&onStateChange('error'));
    socket.addEventListener('message',event=>{
      try{
        const message=JSON.parse(event.data);
        if(message&&message.type&&Object.prototype.hasOwnProperty.call(message,'data')) onMessage&&onMessage(message);
      }catch(_){}
    });
    return socket;
  }

  window.ApiClient={
    hasApiEndpoint,
    hasWsEndpoint,
    getSystemStatus:()=>request('/system/status'),
    getRobots:()=>request('/robots'),
    getRobotDetail:robotId=>request('/robots/'+encodeURIComponent(robotId)),
    getTasks:()=>request('/tasks'),
    getCurrentTask:()=>request('/tasks/current'),
    getEvents:()=>request('/events'),
    getCurrentEvent:()=>request('/events/current'),
    getMap:()=>request('/map'),
    getStatistics:()=>request('/statistics'),
    connectMonitor
  };
})();
