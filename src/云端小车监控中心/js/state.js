(function(){
  const names=['system','robots','tasks','events','map','statistics'];
  const namespace=window.API_CONFIG.CACHE_NAMESPACE;
  const key=name=>namespace+'.'+name;

  function read(name){
    try{
      const raw=localStorage.getItem(key(name));
      return raw?JSON.parse(raw):null;
    }catch(_){return null;}
  }
  function write(name,value){
    if(value===undefined||value===null) return;
    try{localStorage.setItem(key(name),JSON.stringify(value));}catch(_){}
  }
  function seed(defaults){
    names.forEach(name=>{if(read(name)===null&&defaults[name]!==undefined) write(name,defaults[name]);});
  }
  function readAll(defaults={}){
    return names.reduce((state,name)=>{
      const cached=read(name);
      state[name]=cached===null?defaults[name]:cached;
      return state;
    },{});
  }
  function writeMany(partial){
    Object.keys(partial||{}).forEach(name=>{if(names.includes(name)) write(name,partial[name]);});
  }

  window.SearchStateStore={read,write,seed,readAll,writeMany};
})();
