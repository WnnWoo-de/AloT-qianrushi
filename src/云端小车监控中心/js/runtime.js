(function(){
  let socket=null;

  function upsert(list,item,keys){
    const next=Array.isArray(list)?list.slice():[];
    const key=keys.find(name=>item&&item[name]!==undefined);
    if(!key) return next;
    const index=next.findIndex(entry=>entry&&entry[key]===item[key]);
    if(index>=0) next[index]=Object.assign({},next[index],item);
    else next.unshift(item);
    return next;
  }

  function restore(){
    if(!window.SearchClientBridge) return;
    const defaults=SearchClientBridge.getClientSnapshot();
    SearchStateStore.seed(defaults);
    SearchClientBridge.applyServiceState(SearchStateStore.readAll(defaults),{fromCache:true});
  }

  async function syncRest(){
    if(!ApiClient.hasApiEndpoint()||!window.SearchClientBridge) return;
    const requests={
      system:ApiClient.getSystemStatus(),
      robots:ApiClient.getRobots(),
      tasks:ApiClient.getTasks(),
      events:ApiClient.getEvents(),
      map:ApiClient.getMap(),
      statistics:ApiClient.getStatistics()
    };
    const entries=Object.entries(requests);
    const settled=await Promise.allSettled(entries.map(([,promise])=>promise));
    const next={};
    settled.forEach((result,index)=>{
      if(result.status==='fulfilled'&&result.value!==undefined&&result.value!==null) next[entries[index][0]]=result.value;
    });
    if(!Object.keys(next).length) return;
    SearchStateStore.writeMany(next);
    SearchClientBridge.applyServiceState(next,{fromCache:false});
  }

  function onRealtime(message){
    if(!window.SearchClientBridge) return;
    const mapping={robot_update:'robots',task_update:'tasks',event_update:'events',system_update:'system'};
    const entity=mapping[message.type];
    if(!entity) return;
    let value=message.data;
    if(entity==='robots'&&!Array.isArray(value)) value=upsert(SearchStateStore.read('robots'),value,['robot_id','id']);
    if(entity==='tasks'&&!Array.isArray(value)) value=upsert(SearchStateStore.read('tasks'),value,['task_id','id']);
    if(entity==='events'&&!Array.isArray(value)) value=upsert(SearchStateStore.read('events'),value,['event_id','id']);
    SearchStateStore.write(entity,value);
    SearchClientBridge.applyRealtimeMessage(message,value);
  }

  function start(){
    restore();
    syncRest().catch(()=>{});
    if(ApiClient.hasWsEndpoint()) socket=ApiClient.connectMonitor(onRealtime);
  }

  function stop(){if(socket) socket.close();socket=null;}
  window.SearchClientRuntime={start,stop};
})();
