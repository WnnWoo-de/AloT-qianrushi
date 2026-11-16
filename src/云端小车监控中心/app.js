const floorData = {
  1: {
    title: '1F',
    rooms: ['接待大厅','家属等候区','生活照护室','无障碍卫生间','老人餐厅','配餐间','多功能活动室','心理咨询室','家属会客室','护士站','诊疗室','药房/库房','设备间'],
    target: '1F 接待大厅 → 家属等候区',
    suspected: '1F 接待大厅侧',
    tasks: [
      '负责搜索区域：接待大厅、家属等候区、生活照护室、无障碍卫生间。',
      '负责搜索区域：老人餐厅、配餐间、多功能活动室、心理咨询室。',
      '负责搜索区域：护士站、诊疗室、药房/库房、设备间，以及家属会客室邻接区域。',
      '负责搜索区域：D1 负责西侧走廊与左侧出口，D2 负责主走廊及候诊区外侧连通段，D3 负责东侧走廊与右侧出口。'
    ],
    navigation: [
      'M 475 290 L 475 145 L 245 145 L 245 265 L 475 265 L 475 505 L 245 505 L 245 645 L 475 645 L 475 370 L 160 370 L 160 290 L 475 290',
      'M 540 370 L 630 370 L 630 260 L 745 260 L 745 145 L 1010 145 L 1010 260 L 1240 260 L 1240 370 L 930 370 L 930 208 L 630 208 L 630 370 L 540 370',
      'M 980 370 L 980 520 L 750 520 L 750 645 L 980 645 L 1205 645 L 1205 520 L 980 520 L 980 370'
    ]
  },
  2: {
    title: '2F',
    rooms: ['双人病房 A','单人照护室','双人病房 B','无障碍卫生间','康复活动室','理疗室','处置室','候诊休息区','医生办公室','护士站','配药室','康复训练室','医疗设备间'],
    target: '2F 病房区 → 候诊休息区',
    suspected: '2F 候诊休息区附近',
    tasks: [
      '负责搜索区域：双人病房 A、单人照护室、机器人值守充电间、双人病房 B、无障碍卫生间。',
      '负责搜索区域：康复活动室、候诊休息区、两者连通通道、理疗室、处置室、医生办公室，以及电梯前室周边。',
      '负责搜索区域：护士站、配药室、康复训练室、医疗设备间，以及护理区和东侧走廊邻接区域。',
      '负责搜索区域：D1 负责西侧走廊与左侧出口，D2 负责主走廊及候诊区外侧连通段，D3 负责东侧走廊与右侧出口。'
    ],
    navigation: [
      'M 446 128 L 258 128 L 258 145 L 258 128 L 446 128 L 446 252 L 258 252 L 258 260 L 258 252 L 446 252 L 446 386 L 258 386 L 258 520 L 446 520 L 446 642 L 258 642 L 258 648 L 258 642 L 446 642 L 446 386 L 160 386 L 446 386 L 446 128',
      'M 620 386 L 682 386 L 682 303 L 705 303 L 705 255 L 744 255 L 744 208 L 744 191 L 744 145 L 760 145 L 1007 145 L 1007 255 L 1210 255 L 1210 303 L 1210 386 L 930 386 L 930 255 L 1007 255 L 1007 145 L 760 145 L 744 145 L 744 191 L 744 208 L 744 255 L 705 255 L 682 303 L 682 386 L 620 386',
      'M 753 520 L 753 648 L 820 648 L 980 648 L 1188 648 L 1188 520 L 1207 520 L 1207 648 L 1188 648 L 980 648 L 980 520 L 753 520 L 753 648'
    ]
  },
  3: {
    title: '3F',
    rooms: ['观察病房','心理评估室','隔离观察室','营养配餐间','康复评估室','运动训练室','理疗室','康复等候区','医生会诊室','护士站','综合诊疗室','器械训练区','医疗设备间'],
    target: '3F 观察病房 → 康复等候区',
    suspected: '3F 康复等候区',
    tasks: [
      '负责搜索区域：观察病房、心理评估室、隔离观察室。',
      '负责搜索区域：康复评估室、运动训练室、理疗室、康复等候区与医生会诊室。',
      '负责搜索区域：护士站、综合诊疗室、器械训练区、医疗设备间。',
      '负责搜索区域：D1 负责西侧走廊与左侧出口，D2 负责主走廊及候诊区外侧连通段，D3 负责东侧走廊与右侧出口。'
    ],
    navigation: [
      'M 475 635 L 260 635 L 260 510 L 475 510 L 475 270 L 260 270 L 260 145 L 475 145 L 475 370 L 170 370 L 170 635 L 475 635',
      'M 930 370 L 1230 370 L 1230 260 L 1005 260 L 1005 145 L 760 145 L 760 260 L 620 260 L 620 370 L 540 370 L 620 370 L 620 208 L 930 208 L 930 370',
      'M 980 645 L 1200 645 L 1200 520 L 980 520 L 980 370 L 980 520 L 750 520 L 750 645 L 980 645'
    ]
  }
};

const floorVisualData = {
  1: {
    rooms: [
      [91,91,333,92,258,137],[91,200,155,104,168.5,252],[263,200,161,104,343.5,252],[91,468,333,230,258,583],
      [602,91,260,100,732,145],[878,91,190,100,973,145],[1084,91,253,100,1210.5,145],[602,208,360,95,782,260],[1077,208,260,95,1207,260],
      [602,470,220,103,712,526],[838,470,220,103,948,526],[602,590,456,108,830,648],[1077,470,260,228,1207,584]
    ],
    zoneTitles: ['A 区 · 接待照护区','B 区 · 活动服务区','C 区 · 医护支持区'],
    corridorLabels: ['接待主走廊','西侧连廊','东侧服务廊'],
    navigation: {
      navA: floorData[1].navigation[0],
      navB: floorData[1].navigation[1],
      navB2: 'M 1010 145 L 1240 145 L 1240 260 L 1010 260 L 1010 145',
      navC: floorData[1].navigation[2],
      navD: 'M 150 386 L 510 386 L 510 170 L 510 386 L 760 386 L 760 520 L 990 520 L 990 386 L 1288 386 L 990 386 L 760 386 L 510 386 L 150 386'
    },
    zoom: ['补充视图 01 · 接待大厅放大','接待大厅','家属等候区','访客入口','补充视图 02 · 医护支持区放大','护士站 / 诊疗室','药房 / 库房','东侧服务廊']
  },
  3: {
    rooms: [
      [91,91,155,213,168.5,197],[263,91,161,100,343.5,145],[263,208,161,96,343.5,260],[91,468,333,106,258,525],
      [602,91,190,100,697,145],[808,91,250,100,933,145],[1074,91,263,100,1205.5,145],[602,208,220,95,712,260],[838,208,499,95,1087.5,260],
      [602,470,180,228,692,584],[798,470,260,103,928,526],[798,590,260,108,928,648],[1077,470,260,228,1207,584]
    ],
    zoneTitles: ['A 区 · 观察评估区','B 区 · 康复训练区','C 区 · 综合诊疗区'],
    corridorLabels: ['康复主走廊','观察连廊','诊疗连廊'],
    navigation: {
      navA: floorData[3].navigation[0],
      navB: floorData[3].navigation[1],
      navB2: 'M 808 145 L 1058 145 L 1058 260 L 838 260 L 838 208 L 808 208 L 808 145',
      navC: floorData[3].navigation[2],
      navD: 'M 165 386 L 512 386 L 512 635 L 512 386 L 710 386 L 710 208 L 980 208 L 980 386 L 1280 386 L 980 386 L 980 645 L 980 386 L 512 386 L 165 386'
    },
    zoom: ['补充视图 01 · 康复等候区放大','康复等候区','医生会诊室','复核点','补充视图 02 · 综合诊疗区放大','护士站 / 综合诊疗室','器械训练区','诊疗连廊']
  }
};

const floorRobotBehavior = {
  1: {
    A:{speedMultiplier:1.08,offsetDelta:0.04},
    B:{speedMultiplier:0.94,offsetDelta:0.08},
    C:{speedMultiplier:1.03},
    D:{speedMultiplier:0.90}
  },
  3: {
    A:{speedMultiplier:0.92,offsetDelta:0.07},
    B:{speedMultiplier:1.08},
    C:{speedMultiplier:0.96,offsetDelta:0.11},
    D:{speedMultiplier:1.06,offsetDelta:0.05}
  }
};

const remoteRobotState = new Map();


let currentFloor = 2;
let animationStart = performance.now();
let lastUiUpdate = 0;
const groupProgress = {A:0, B:0, C:0, D:0};
const robotConfig = [
  {robot:'robotA1', network:'navA', group:'A', speed:0.0000068, offset:0.35, seed:0.4},
  {robot:'robotA2', network:'navA', group:'A', speed:0.0000058, offset:0.52, seed:1.2},
  {robot:'robotA3', network:'navA', group:'A', speed:0.0000063, offset:0.50, seed:2.0},
  {robot:'robotB1', network:'navB', group:'B', speed:0.0000059, offset:0.18, seed:2.8},
  {robot:'robotB2', network:'navB2', group:'B', speed:0.0000048, offset:0.18, seed:3.5},
  {robot:'robotB3', network:'navB', group:'B', speed:0.0000061, offset:0.35, seed:4.3},
  {robot:'robotC1', network:'navC', group:'C', speed:0.0000057, offset:0.10, seed:5.1},
  {robot:'robotC2', network:'navC', group:'C', speed:0.0000060, offset:0.45, seed:5.9},
  {robot:'robotC3', network:'navC', group:'C', speed:0.0000062, offset:0.80, seed:6.7},
  {robot:'robotD1', network:'navD', group:'D', speed:0.0000042, offset:0.10, seed:7.5},
  {robot:'robotD2', network:'navD', group:'D', speed:0.0000043, offset:0.780, seed:8.3},
  {robot:'robotD3', network:'navD', group:'D', speed:0.0000040, offset:0.62, seed:9.1}
];
const beaconConfig = [
  {id:'beaconA', network:'navA', speed:0.000022, offset:0.32},
  {id:'beaconB', network:'navB', speed:0.000020, offset:0.48},
  {id:'beaconC', network:'navC', speed:0.000021, offset:0.75}
];


const scenarioTiming = { alert:0, dispatch:7100, relief:15000, confirm:24000 };
const eventMotionTiming = { d1InspectEnd:6600, d1MoveEnd:16800, d2FastStart:12500, d2MoveEnd:18000 };
let scenarioStart = performance.now();
let scenarioPhase = -1;
let scenarioPlan = null;
const robotHeadingState = {};
let fitScale = 1;
let baseLeft = 0;
let baseTop = 0;
let userZoom = 1;
let panX = 0;
let panY = 0;
let dragState = null;
const VIEW_STATE_KEY = 'elderlyCareZoomViewState';

function setText(id, text){
  const el = document.getElementById(id);
  if(el) el.textContent = text;
}

function setRobotLabel(robotId, text){
  const robot = document.getElementById(robotId);
  const label = robot?.querySelector('.robot-tag text');
  if(label) label.textContent = text;
}

function readRobotPosition(robotId){
  const robot = document.getElementById(robotId);
  const transform = robot?.getAttribute('transform') || '';
  const match = transform.match(/translate\(([-\d.]+)[ ,]+([-\d.]+)\)/);
  if(match) return {x:Number(match[1]), y:Number(match[2])};
  return {x:0,y:0};
}

function smoothCurvePoints(points, iterations=2){
  let result=points.map(point=>({x:point.x,y:point.y}));
  for(let pass=0;pass<iterations;pass++){
    const next=[result[0]];
    for(let i=0;i<result.length-1;i++){
      const a=result[i], b=result[i+1];
      next.push({x:a.x*.75+b.x*.25,y:a.y*.75+b.y*.25});
      next.push({x:a.x*.25+b.x*.75,y:a.y*.25+b.y*.75});
    }
    next.push(result[result.length-1]);
    result=next;
  }
  return result;
}

function moveRobotAlongPoints(robotId, points, progress, updateHeading=true){
  const robot = document.getElementById(robotId);
  if(!robot || !points || points.length < 2) return;
  const curvePoints=smoothCurvePoints(points,2);
  const lengths=[];
  let total=0;
  for(let i=0;i<curvePoints.length-1;i++){
    const dx=curvePoints[i+1].x-curvePoints[i].x;
    const dy=curvePoints[i+1].y-curvePoints[i].y;
    const len=Math.hypot(dx,dy);
    lengths.push(len); total+=len;
  }
  let distance=Math.max(0,Math.min(1,progress))*total;
  let index=0;
  while(index<lengths.length-1 && distance>lengths[index]){distance-=lengths[index]; index++;}
  const a=curvePoints[index], b=curvePoints[index+1];
  const t=lengths[index] ? distance/lengths[index] : 0;
  const x=a.x+(b.x-a.x)*t;
  const y=a.y+(b.y-a.y)*t;
  const targetAngle=Math.atan2(b.y-a.y,b.x-a.x)*180/Math.PI+90;
  robot.setAttribute('transform',`translate(${x} ${y})`);
  const heading=robot.querySelector('.robot-heading');
  if(heading && updateHeading){
    let current = robotHeadingState[robotId];
    if(typeof current !== 'number') current = targetAngle;
    let delta = ((targetAngle - current + 540) % 360) - 180;
    const factor = robotId === 'robotD1' ? 0.060 : 0.120;
    const maxStep = robotId === 'robotD1' ? 1.25 : 1.8;
    const step = Math.max(-maxStep, Math.min(maxStep, delta * factor));
    current += step;
    robotHeadingState[robotId] = current;
    heading.setAttribute('transform',`rotate(${current})`);
  }
}

const navigationGraphCache = new Map();
const robotNavigationState = new Map();

function parseNavigationPoints(pathElement){
  const d=pathElement?.getAttribute('d')||'';
  const points=[];
  const pattern=/[ML]\s*(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)/gi;
  let match;
  while((match=pattern.exec(d))!==null) points.push({x:Number(match[1]),y:Number(match[2])});
  return points;
}

function getNavigationGraph(networkId){
  const element=document.getElementById(networkId);
  if(!element) return null;
  const signature=element.getAttribute('d')||'';
  const cached=navigationGraphCache.get(networkId);
  if(cached?.signature===signature) return cached;

  const source=parseNavigationPoints(element);
  const nodes=[];
  const adjacency=[];
  const indexByKey=new Map();
  const nodeIndex=point=>{
    const key=`${point.x.toFixed(2)},${point.y.toFixed(2)}`;
    if(indexByKey.has(key)) return indexByKey.get(key);
    const index=nodes.length;
    nodes.push({x:point.x,y:point.y});
    adjacency.push([]);
    indexByKey.set(key,index);
    return index;
  };
  const connect=(a,b)=>{
    if(a===b) return;
    const distance=Math.hypot(nodes[a].x-nodes[b].x,nodes[a].y-nodes[b].y);
    if(!distance) return;
    if(!adjacency[a].some(edge=>edge.to===b)) adjacency[a].push({to:b,cost:distance});
    if(!adjacency[b].some(edge=>edge.to===a)) adjacency[b].push({to:a,cost:distance});
  };
  for(let i=0;i<source.length;i++){
    const current=nodeIndex(source[i]);
    if(i>0) connect(nodeIndex(source[i-1]),current);
  }
  const graph={networkId,signature,nodes,adjacency,element};
  navigationGraphCache.set(networkId,graph);
  return graph;
}

function nearestNavigationNode(graph, point){
  if(!graph?.nodes?.length||!point) return -1;
  let best=-1;
  let bestDistance=Infinity;
  graph.nodes.forEach((node,index)=>{
    const distance=Math.hypot(node.x-point.x,node.y-point.y);
    if(distance<bestDistance){best=index;bestDistance=distance;}
  });
  return best;
}

function shortestNavigationNodes(graph,startIndex,goalIndex){
  const count=graph?.nodes?.length||0;
  if(startIndex<0||goalIndex<0||!count) return [];
  const distance=Array(count).fill(Infinity);
  const previous=Array(count).fill(-1);
  const visited=Array(count).fill(false);
  distance[startIndex]=0;

  for(let step=0;step<count;step++){
    let current=-1;
    let currentDistance=Infinity;
    for(let i=0;i<count;i++){
      if(!visited[i]&&distance[i]<currentDistance){current=i;currentDistance=distance[i];}
    }
    if(current<0||current===goalIndex) break;
    visited[current]=true;
    for(const edge of graph.adjacency[current]){
      const nextDistance=distance[current]+edge.cost;
      if(nextDistance<distance[edge.to]){
        distance[edge.to]=nextDistance;
        previous[edge.to]=current;
      }
    }
  }

  const path=[];
  let cursor=goalIndex;
  while(cursor>=0){
    path.push(cursor);
    if(cursor===startIndex) break;
    cursor=previous[cursor];
  }
  if(path[path.length-1]!==startIndex) return [];
  return path.reverse();
}

function compactPath(points){
  const result=[];
  for(const point of points||[]){
    if(!point||!Number.isFinite(point.x)||!Number.isFinite(point.y)) continue;
    const last=result[result.length-1];
    if(!last||Math.hypot(point.x-last.x,point.y-last.y)>0.5) result.push({x:point.x,y:point.y});
  }
  return result;
}

function projectPointOnGraph(graph, point){
  if(!graph||!point) return null;
  let best=null;
  let bestDistance=Infinity;
  for(let from=0;from<graph.nodes.length;from++){
    const a=graph.nodes[from];
    for(const edge of graph.adjacency[from]){
      if(edge.to<from) continue;
      const b=graph.nodes[edge.to];
      const dx=b.x-a.x,dy=b.y-a.y;
      const length2=dx*dx+dy*dy;
      const t=length2?Math.max(0,Math.min(1,((point.x-a.x)*dx+(point.y-a.y)*dy)/length2)):0;
      const projected={x:a.x+dx*t,y:a.y+dy*t};
      const distance=Math.hypot(projected.x-point.x,projected.y-point.y);
      if(distance<bestDistance){
        best={point:projected,from,to:edge.to,t};
        bestDistance=distance;
      }
    }
  }
  return best;
}

function projectPointToNavigation(networkId, point){
  const projection=projectPointOnGraph(getNavigationGraph(networkId),point);
  return projection?.point||point;
}

function planNavigationPath(networkId,startPoint,goalPoint){
  const graph=getNavigationGraph(networkId);
  if(!graph) return compactPath([startPoint,goalPoint]);
  const startProjection=projectPointOnGraph(graph,startPoint);
  const goalProjection=projectPointOnGraph(graph,goalPoint);
  if(!startProjection||!goalProjection) return compactPath([startPoint,goalPoint]);

  let bestPath=null;
  let bestLength=Infinity;
  const sameEdge=(startProjection.from===goalProjection.from&&startProjection.to===goalProjection.to)||
    (startProjection.from===goalProjection.to&&startProjection.to===goalProjection.from);
  if(sameEdge){
    const direct=compactPath([startPoint,startProjection.point,goalProjection.point,goalPoint]);
    bestPath=direct;
    bestLength=polylineLength(direct);
  }

  const startEnds=[startProjection.from,startProjection.to];
  const goalEnds=[goalProjection.from,goalProjection.to];
  for(const startIndex of startEnds){
    for(const goalIndex of goalEnds){
      const indices=shortestNavigationNodes(graph,startIndex,goalIndex);
      if(!indices.length) continue;
      const path=compactPath([
        startPoint,
        startProjection.point,
        ...indices.map(index=>graph.nodes[index]),
        goalProjection.point,
        goalPoint
      ]);
      const length=polylineLength(path);
      if(length<bestLength){bestPath=path;bestLength=length;}
    }
  }
  return bestPath||compactPath([startPoint,startProjection.point,goalProjection.point,goalPoint]);
}

function polylineLength(points){
  let total=0;
  for(let i=0;i<(points?.length||0)-1;i++) total+=Math.hypot(points[i+1].x-points[i].x,points[i+1].y-points[i].y);
  return total;
}

function pointAtDistanceFromEnd(points,distance){
  if(!points?.length) return null;
  let remaining=Math.max(0,distance);
  for(let i=points.length-1;i>0;i--){
    const a=points[i-1],b=points[i];
    const segment=Math.hypot(b.x-a.x,b.y-a.y);
    if(remaining<=segment){
      const t=segment?remaining/segment:0;
      return {x:b.x+(a.x-b.x)*t,y:b.y+(a.y-b.y)*t};
    }
    remaining-=segment;
  }
  return {x:points[0].x,y:points[0].y};
}

function firstDirectionChangeIndex(points){
  for(let i=1;i<(points?.length||0)-1;i++){
    const a=points[i-1],b=points[i],c=points[i+1];
    const angleA=Math.atan2(b.y-a.y,b.x-a.x);
    const angleB=Math.atan2(c.y-b.y,c.x-b.x);
    const delta=Math.abs(((angleB-angleA+Math.PI*3)%(Math.PI*2))-Math.PI);
    if(delta>Math.PI/5) return i;
  }
  return Math.max(1,Math.floor((points?.length||2)/2));
}

function navigationSeedPoint(networkId,fraction){
  const element=document.getElementById(networkId);
  if(!element) return {x:0,y:0};
  const length=element.getTotalLength();
  const value=((fraction%1)+1)%1;
  const point=element.getPointAtLength(value*length);
  return {x:point.x,y:point.y};
}

function selectPatrolGoal(graph,currentPoint,cfg,cycle){
  const candidates=graph.nodes
    .map((node,index)=>({node,index,distance:Math.hypot(node.x-currentPoint.x,node.y-currentPoint.y)}))
    .filter(item=>item.distance>90)
    .sort((a,b)=>b.distance-a.distance);
  const pool=candidates.length?candidates:graph.nodes.map((node,index)=>({node,index,distance:0}));
  const span=Math.max(1,Math.ceil(pool.length*0.65));
  const seed=Math.floor((cfg.seed||0)*1000)+currentFloor*97+cycle*17;
  return pool[Math.abs(seed)%span]?.node||graph.nodes[0];
}

function resetNavigationRuntime(){
  navigationGraphCache.clear();
  robotNavigationState.clear();
}

function moveRobotByNavigation(cfg,now){
  const graph=getNavigationGraph(cfg.network);
  const robot=document.getElementById(cfg.robot);
  if(!graph||!robot||graph.nodes.length<2) return;
  const behavior=floorRobotBehavior[currentFloor]?.[cfg.group]||{};
  let state=robotNavigationState.get(cfg.robot);
  const signature=`${currentFloor}:${graph.signature}`;
  if(!state||state.signature!==signature){
    const offset=cfg.offset+(behavior.offsetDelta||0);
    const start=navigationSeedPoint(cfg.network,offset);
    state={signature,cycle:0,current:start,path:null,startedAt:now,duration:0,visited:new Set()};
    robotNavigationState.set(cfg.robot,state);
  }

  if(!state.path||now>=state.startedAt+state.duration){
    if(state.path?.length) state.current={...state.path[state.path.length-1]};
    const goal=selectPatrolGoal(graph,state.current,cfg,state.cycle++);
    state.path=planNavigationPath(cfg.network,state.current,goal);
    const distance=Math.max(1,polylineLength(state.path));
    const networkLength=Math.max(1,graph.element.getTotalLength());
    const speed=Math.max(0.0045,networkLength*cfg.speed*(behavior.speedMultiplier||1));
    state.duration=Math.max(3200,distance/speed);
    state.startedAt=now;
    const goalIndex=nearestNavigationNode(graph,goal);
    if(goalIndex>=0) state.visited.add(goalIndex);
  }

  const progress=Math.max(0,Math.min(1,(now-state.startedAt)/state.duration));
  moveRobotAlongPoints(cfg.robot,state.path,progress,true);
  state.current=readRobotPosition(cfg.robot);
  if(cfg.robot.endsWith('1')) groupProgress[cfg.group]=Math.min(1,state.visited.size/Math.max(1,graph.nodes.length));
}

function setRobotLookAt(robotId, targetPoint, factor = 0.14, maxStep = 1.2){
  const robot = document.getElementById(robotId);
  const heading = robot?.querySelector('.robot-heading');
  if(!robot || !heading || !targetPoint) return;
  const pos = readRobotPosition(robotId);
  const dx = targetPoint.x - pos.x;
  const dy = targetPoint.y - pos.y;
  if(Math.hypot(dx,dy) < 1) return;
  const targetAngle = Math.atan2(dy, dx) * 180 / Math.PI + 90;
  let current = robotHeadingState[robotId];
  if(typeof current !== 'number') current = targetAngle;
  let delta = ((targetAngle - current + 540) % 360) - 180;
  const step = Math.max(-maxStep, Math.min(maxStep, delta * factor));
  current += step;
  robotHeadingState[robotId] = current;
  heading.setAttribute('transform', `rotate(${current})`);
}

function setCardStatus(id, text, className=''){
  const el=document.getElementById(id);
  if(!el) return;
  el.textContent=text;
  el.classList.remove('scenario-dispatch','scenario-relief');
  if(className) el.classList.add(className);
}

function resetScenarioVisuals(){
  const summary=document.getElementById('eventSummary');
  summary?.classList.add('scenario-summary-hidden');
  summary?.classList.remove('scenario-summary-visible');
  const alert=document.getElementById('waitingAlert');
  alert?.classList.add('scenario-alert-hidden');
  alert?.classList.remove('scenario-alert-visible');
  ['robotD1','robotD2'].forEach(id=>document.getElementById(id)?.classList.remove('scenario-emergency','scenario-relief','scenario-confirm','scenario-inspect','scenario-support'));
  scenarioPlan=null;
  delete robotHeadingState.robotD1;
  delete robotHeadingState.robotD2;
  document.querySelectorAll('.robot-card').forEach(card=>card.classList.remove('scenario-card-active'));
  setRobotLabel('robotA1','机器人 A1');
  setRobotLabel('robotB1','机器人 B1');
  setRobotLabel('robotB2','机器人 B2');
  setRobotLabel('robotB3','机器人 B3');
  setRobotLabel('robotD1','走廊 D1');
  setRobotLabel('robotD2','D2 · 补位');
  setCardStatus('statusA','巡逻中');
  setCardStatus('statusB','巡逻中');
  setCardStatus('statusC','巡逻中');
  setCardStatus('statusD','巡逻中');
  setText('taskA','负责搜索区域：双人病房 A、单人照护室、机器人值守充电间、双人病房 B、无障碍卫生间。');
  setText('taskB','负责搜索区域：康复活动室、候诊休息区、两者连通通道、理疗室、处置室、医生办公室，以及电梯前室周边。');
  setText('taskC','负责搜索区域：护士站、配药室、康复训练室、医疗设备间，以及护理区和东侧走廊邻接区域。');
  setText('taskD','负责搜索区域：D1 负责西侧走廊与左侧出口，D2 负责主走廊及候诊区外侧连通段，D3 负责东侧走廊与右侧出口。');
}

function enterScenarioPhase(phase){
  scenarioPhase=phase;
  const summary=document.getElementById('eventSummary');
  const alert=document.getElementById('waitingAlert');
  const cardD=document.querySelector('.robot-card-d');

  if(phase===0){
    resetScenarioVisuals();
    setText('missionTitleText','日常巡检运行中');
    setText('missionTargetText',`${floorData[currentFloor].title} 全区域巡检`);
    setText('missionSystemText','巡检链路正常 · 未发现异常');
    setText('dispatchState','协同均衡');
    setText('cooperationMode','常规分区巡检');
    setText('eventTypeText','暂无异常');
    setText('eventLevelText','正常');
    setText('eventPosText','—');
    setText('eventLinkText','—');
    setText('taskStateText','日常巡检中');
    setText('riskZoneText','暂无异常区域');
    setText('strategyText','分区并行巡检');
    setText('closedLoopText','运行正常');
    const data=floorData[currentFloor];
    setText('taskA',data.tasks[0]); setText('taskB',data.tasks[1]); setText('taskC',data.tasks[2]); setText('taskD',data.tasks[3]||'负责搜索区域：D1 负责西侧走廊与左侧出口，D2 负责主走廊及候诊区外侧连通段，D3 负责东侧走廊与右侧出口。');
    return;
  }

  summary?.classList.remove('scenario-summary-hidden');
  summary?.classList.add('scenario-summary-visible');
  alert?.classList.remove('scenario-alert-hidden');
  alert?.classList.add('scenario-alert-visible');
  const emergencyActive = phase >= 2;
  setText('missionTitleText', emergencyActive ? '西侧走廊紧急事件' : 'D1 任务检查中');
  setText('missionTargetText', emergencyActive ? '2F 西侧走廊 · 康复活动室左侧' : '2F 西侧走廊转角巡检');
  setText('eventTypeText', emergencyActive ? '走廊异常事件' : '任务检查');
  setText('eventLevelText', phase===1 ? '常规巡检' : phase===2 ? '紧急事件' : phase===3 ? '补位处置' : '协同处置');
  setText('eventPosText', emergencyActive ? '2F 西侧走廊 · 康复活动室左侧' : '2F 西侧走廊转角');
  setText('taskStateText', emergencyActive ? 'D 区局部联动已触发' : 'D1 任务检查中');
  setText('riskZoneText', emergencyActive ? '西侧走廊 · 康复活动室左侧' : '西侧走廊转角');

  setCardStatus('statusA','巡逻中');
  setCardStatus('statusB','巡逻中');
  setCardStatus('statusC','巡逻中');
  setText('taskA',floorData[currentFloor].tasks[0]);
  setText('taskB',floorData[currentFloor].tasks[1]);
  setText('taskC',floorData[currentFloor].tasks[2]);

  if(phase===1){
    setText('missionSystemText','D1 一边行进一边慢慢转头执行任务检查 · D2 从更远的后方以正常速度同步补位');
    setText('dispatchState','D1 任务检查');
    setText('cooperationMode','D1 边走边检查 + D2 同步补位');
    setText('eventLinkText','D1 边走边转头检查 · 转过头后发现异常 · D2 从较远后方持续跟进补位');
    setText('strategyText','D1 从消防栓右侧起步后，一边向西侧走廊转角行进，一边缓慢转头执行任务检查；D2 的初始位置与 D1 拉开更大间距，因此可从一开始就以正常较快速度在后方跟进，此时尚未进入紧急事件状态。');
    setRobotLabel('robotD1','D1 · 任务检查');
    setRobotLabel('robotD2','D2 · 补位');
    document.getElementById('robotD1')?.classList.remove('scenario-confirm','scenario-emergency');
    document.getElementById('robotD1')?.classList.add('scenario-inspect');
    document.getElementById('robotD2')?.classList.remove('scenario-emergency','scenario-inspect');
    document.getElementById('robotD2')?.classList.add('scenario-support');
    setCardStatus('statusD','D1 检查中');
    setText('taskD','D1 从消防栓右侧起步，边走边慢慢转头，按任务检查路线前往西侧走廊转角；D2 从更远的后方以正常速度跟进补位，保持不超前；D3 继续右侧正常巡逻。');
    cardD?.classList.add('scenario-card-active');
  }

  if(phase===2){
    setText('missionSystemText','D1 转过头后继续保持任务检查 0.5 秒，随后触发紧急事件；此时仅 D1 变红，D2 保持补位状态继续跟进');
    setText('dispatchState','紧急事件触发');
    setText('cooperationMode','D1 紧急事件 + D2 补位');
    setText('eventLinkText','D1 转过头后保持检查 0.5 秒 · 紧急事件触发 · D1 转为红色 · D2 持续补位');
    setText('strategyText','D1 在更靠右的转弯位置边走边完成转头后，继续保持原本的任务检查状态 0.5 秒；随后立即切换为紧急事件并变红，D2 保持原本颜色继续执行补位。');
    setCardStatus('statusD','D1 紧急事件 + D2 补位','scenario-dispatch');
    setText('taskD','D1 在更靠前的位置边走边转头，转过头后仍保持任务检查 0.5 秒，随后发现康复活动室左侧异常并立即转为紧急事件；仅 D1 变红，D2 继续沿 D1 身后路线跟进补位；其余机器人保持正常巡逻。');
    setRobotLabel('robotD1','D1 · 紧急事件');
    setRobotLabel('robotD2','D2 · 补位');
    document.getElementById('robotD1')?.classList.remove('scenario-inspect');
    document.getElementById('robotD1')?.classList.add('scenario-emergency');
    document.getElementById('robotD2')?.classList.remove('scenario-emergency','scenario-inspect');
    document.getElementById('robotD2')?.classList.add('scenario-support');
    cardD?.classList.add('scenario-card-active');
  }

  if(phase===3){
    setText('missionSystemText','D1 保持紧急事件状态并继续前往异常点 · D2 在后方保持补位间距跟随，持续覆盖 D1 身后的巡检盲区');
    setText('dispatchState','D2 补位中');
    setText('cooperationMode','D1 紧急事件 + D2 盲区补位');
    setText('eventLinkText','D1 保持紧急事件并向异常点前移 · D2 沿 D1 经过的路径跟随 · 始终保留一段补位距离');
    setText('strategyText','D1 保持紧急事件状态向西侧走廊异常点前移；D2 从更远的初始位置以正常较快速度跟进，并沿 D1 经过的路线进入补位区，始终稍微落后 D1 一段距离覆盖其身后盲区，避免贴得过近。');
    setCardStatus('statusD','D2 补位中','scenario-dispatch');
    setText('taskD','D1 前往西侧走廊事件点后始终保持紧急事件状态；D2 从更远处开始以正常速度跟进，沿 D1 身后路线持续补位并保留稍微更靠后的间距，不贴近 D1；D3 继续正常巡逻。');
    setRobotLabel('robotD1','D1 · 紧急事件');
    setRobotLabel('robotD2','D2 · 补位');
    document.getElementById('robotD1')?.classList.remove('scenario-confirm');
    document.getElementById('robotD2')?.classList.remove('scenario-emergency','scenario-inspect');
    document.getElementById('robotD2')?.classList.add('scenario-support');
    cardD?.classList.add('scenario-card-active');
  }

  if(phase===4){
    setText('missionTitleText','D1 紧急事件 · D2 盲区补位');
    setText('missionSystemText','D1 已到异常点并持续保持紧急事件；D2 保持在 D1 身后一段补位距离并朝向 D1');
    setText('dispatchState','补位完成');
    setText('cooperationMode','D1 紧急事件 + D2 盲区补位');
    setText('eventLinkText','D1 在异常点持续保持紧急事件 · D2 在身后保持补位间距持续覆盖盲区');
    setText('strategyText','D1 在异常点持续保持紧急事件状态；D2 沿 D1 的行进路线跟到后方补位位置，与 D1 保持清晰且稍微更靠后的协同间距，并持续朝向 D1；其余机器人照常巡逻。');
    setText('closedLoopText','D 区联动处置中');
    setCardStatus('statusD','D1 紧急事件 + D2 补位到位','scenario-dispatch');
    setText('taskD','D1 到达西侧走廊事件点后始终保持紧急事件状态；D2 沿 D1 身后路线完成补位，与 D1 保持一段稳定且稍微更靠后的距离并朝向 D1；D3 全程正常巡逻。');
    setRobotLabel('robotD1','D1 · 紧急事件');
    setRobotLabel('robotD2','D2 · 补位');
    document.getElementById('robotD2')?.classList.remove('scenario-emergency','scenario-inspect');
    document.getElementById('robotD2')?.classList.add('scenario-support');
    cardD?.classList.add('scenario-card-active');
  }
}
function restartScenario(){
  scenarioStart=performance.now();
  scenarioPhase=-1;
  scenarioPlan=null;
  delete robotHeadingState.robotD1;
  delete robotHeadingState.robotD2;
  enterScenarioPhase(currentFloor===2 ? 1 : 0);
}

function updateScenario(now){
  if(currentFloor!==2) return;
  const elapsed=now-scenarioStart;
  const nextPhase=elapsed<scenarioTiming.alert?0:elapsed<scenarioTiming.dispatch?1:elapsed<scenarioTiming.relief?2:elapsed<scenarioTiming.confirm?3:4;
  if(nextPhase!==scenarioPhase) enterScenarioPhase(nextPhase);

  const hermiteProgress=(value,startSlope,endSlope)=>{
    const t=Math.max(0,Math.min(1,value));
    const t2=t*t;
    const t3=t2*t;
    return (-2*t3+3*t2)+startSlope*(t3-2*t2+t)+endSlope*(t3-t2);
  };

  if(!scenarioPlan){
    const d1Cfg=robotConfig.find(item=>item.robot==='robotD1');
    const d2Cfg=robotConfig.find(item=>item.robot==='robotD2');
    const hotspot=document.querySelector('#waitingAlert .hotspot-core');
    const eventPoint={x:Number(hotspot?.getAttribute('cx')||0),y:Number(hotspot?.getAttribute('cy')||0)};
    const fireRect=document.querySelector('.fire-marker rect');
    const fireX=Number(fireRect?.getAttribute('x')||0);
    const fireY=Number(fireRect?.getAttribute('y')||0);
    const fireWidth=Number(fireRect?.getAttribute('width')||0);
    const fireHeight=Number(fireRect?.getAttribute('height')||0);
    const fireCenter={x:fireX+fireWidth/2,y:fireY+fireHeight/2};
    const d1Reference={x:fireCenter.x+Math.max(42,fireWidth*2.6),y:fireCenter.y+Math.max(28,fireHeight*2.1)};
    const d1Start=projectPointToNavigation(d1Cfg.network,d1Reference);
    const d2Start=projectPointToNavigation(d2Cfg.network,{x:d1Start.x+Math.max(150,fireWidth*8.5),y:d1Start.y});
    const d1Path=planNavigationPath(d1Cfg.network,d1Start,eventPoint);
    const cornerIndex=firstDirectionChangeIndex(d1Path);
    const inspectPath=compactPath(d1Path.slice(0,cornerIndex+1));
    const eventPath=compactPath(d1Path.slice(cornerIndex));
    const d2Goal=pointAtDistanceFromEnd(d1Path,Math.max(190,fireHeight*11));
    const d2Path=planNavigationPath(d2Cfg.network,d2Start,d2Goal);
    scenarioPlan={eventPoint,inspectPath,eventPath,d2Path};
  }

  if(elapsed<eventMotionTiming.d1InspectEnd){
    const turning=elapsed>1800;
    const progress=hermiteProgress(elapsed/eventMotionTiming.d1InspectEnd,0,1);
    moveRobotAlongPoints('robotD1',scenarioPlan.inspectPath,progress,!turning);
    if(turning) setRobotLookAt('robotD1',scenarioPlan.eventPoint,0.018,1.0);
  }else{
    const progress=hermiteProgress((elapsed-eventMotionTiming.d1InspectEnd)/(eventMotionTiming.d1MoveEnd-eventMotionTiming.d1InspectEnd),0.58,0);
    moveRobotAlongPoints('robotD1',scenarioPlan.eventPath,progress,false);
    setRobotLookAt('robotD1',scenarioPlan.eventPoint,0.024,1.0);
  }

  const d2Progress=hermiteProgress(elapsed/eventMotionTiming.d2MoveEnd,0,0);
  moveRobotAlongPoints('robotD2',scenarioPlan.d2Path,d2Progress,elapsed<eventMotionTiming.d2FastStart-1800);
  if(elapsed>=eventMotionTiming.d2FastStart-1800){
    const arrived=elapsed>=eventMotionTiming.d2MoveEnd;
    setRobotLookAt('robotD2',readRobotPosition('robotD1'),arrived?0.065:0.040,arrived?1.5:1.25);
  }
}

function saveViewState(){
  try{
    localStorage.setItem(VIEW_STATE_KEY, JSON.stringify({
      userZoom, panX, panY, currentFloor
    }));
  }catch(err){}
}

function restoreViewState(){
  try{
    const raw = localStorage.getItem(VIEW_STATE_KEY);
    if(!raw) return;
    const state = JSON.parse(raw);
    if(typeof state.userZoom === 'number') userZoom = Math.max(1, Math.min(4, state.userZoom));
    if(typeof state.panX === 'number') panX = state.panX;
    if(typeof state.panY === 'number') panY = state.panY;
    if(typeof state.currentFloor === 'number') currentFloor = state.currentFloor;
  }catch(err){}
}

function applyViewTransform(){
  const screen = document.getElementById('screen');
  const totalScale = fitScale * userZoom;
  screen.style.transform = `translate(${baseLeft + panX}px, ${baseTop + panY}px) scale(${totalScale})`;
  saveViewState();
}

function resizeScreen(){
  fitScale = Math.min(window.innerWidth / 1920, window.innerHeight / 1080);
  baseLeft = (window.innerWidth - 1920 * fitScale) / 2;
  baseTop = (window.innerHeight - 1080 * fitScale) / 2;
  applyViewTransform();
}

function setUserZoom(nextZoom, centerX = window.innerWidth / 2, centerY = window.innerHeight / 2){
  const oldTotal = fitScale * userZoom;
  const screenX = (centerX - (baseLeft + panX)) / oldTotal;
  const screenY = (centerY - (baseTop + panY)) / oldTotal;
  userZoom = Math.max(1, Math.min(4, nextZoom));
  const newTotal = fitScale * userZoom;
  panX = centerX - baseLeft - screenX * newTotal;
  panY = centerY - baseTop - screenY * newTotal;
  applyViewTransform();
}

function resetView(){
  userZoom = 1;
  panX = 0;
  panY = 0;
  applyViewTransform();
}

function chinaTimeParts(){
  const parts = new Intl.DateTimeFormat('zh-CN', {
    timeZone:'Asia/Shanghai', year:'numeric', month:'2-digit', day:'2-digit',
    weekday:'long', hour:'2-digit', minute:'2-digit', second:'2-digit', hourCycle:'h23'
  }).formatToParts(new Date());
  const value = type => parts.find(part => part.type === type)?.value || '';
  return {
    year:value('year'), month:value('month'), day:value('day'), weekday:value('weekday'),
    hour:value('hour'), minute:value('minute'), second:value('second')
  };
}

function updateClock(){
  const t = chinaTimeParts();
  document.getElementById('clock').textContent = `北京时间 ${t.year}年${t.month}月${t.day}日 ${t.weekday} ${t.hour}:${t.minute}:${t.second}`;
  document.getElementById('mapUpdated').textContent = `数据刷新 ${t.hour}:${t.minute}:${t.second}`;
}

function updateLiveUi(){
  const values=[];
  for(const group of ['A','B','C','D']){
    const percent=Math.round(groupProgress[group]*100);
    values.push(percent);
    const bar=document.getElementById(`progress${group}`);
    const text=document.getElementById(`progress${group}Text`);
    if(bar) bar.style.width=`${percent}%`;
    if(text) text.textContent=`实时进度 ${percent}%`;
  }
  const avg=Math.round(values.reduce((a,b)=>a+b,0)/values.length);
  const diff=Math.max(...values)-Math.min(...values);
  const overlap=Math.max(3,Math.round(diff/10));
  const coverage=Math.min(100,Math.max(90,avg));
  setText('coverageRate',`${coverage}%`);
  setText('overlapRate',`${overlap}%`);
}

function moveRobots(now){
  for(const cfg of robotConfig){
    const overridden=currentFloor===2&&(cfg.robot==='robotD1'||cfg.robot==='robotD2');
    if(overridden) continue;
    const robot=document.getElementById(cfg.robot);
    if(!robot) continue;
    const remote=remoteRobotState.get(cfg.robot);
    if(remote&&now-remote.receivedAt<5000&&remote.position&&Number.isFinite(Number(remote.position.x))&&Number.isFinite(Number(remote.position.y))){
      robot.setAttribute('transform',`translate(${Number(remote.position.x)} ${Number(remote.position.y)})`);
      const heading=robot.querySelector('.robot-heading');
      if(heading&&Number.isFinite(Number(remote.heading))) heading.setAttribute('transform',`rotate(${Number(remote.heading)})`);
      continue;
    }
    moveRobotByNavigation(cfg,now);
  }

  for(const cfg of beaconConfig){
    const network=document.getElementById(cfg.network);
    const beacon=document.getElementById(cfg.id);
    if(!network||!beacon) continue;
    const length=network.getTotalLength();
    const progress=((now-animationStart)*cfg.speed+cfg.offset)%1;
    const pos=network.getPointAtLength(progress*length);
    beacon.setAttribute('cx',pos.x);
    beacon.setAttribute('cy',pos.y);
  }

  updateScenario(now);
  if(now-lastUiUpdate>180){updateLiveUi();lastUiUpdate=now;}
  requestAnimationFrame(moveRobots);
}


const baseFloorVisual = (()=>{
  const rooms=[...document.querySelectorAll('.room')].map(room=>{
    const rect=room.querySelector('rect');
    const text=room.querySelector('text');
    return {
      rect:['x','y','width','height'].map(name=>rect.getAttribute(name)),
      text:[text.getAttribute('x'),text.getAttribute('y')]
    };
  });
  return {
    rooms,
    zoneTitles:[...document.querySelectorAll('.zone-title text')].map(el=>el.textContent),
    corridorLabels:[...document.querySelectorAll('.corridor-overlay-layer .corridor-label')].map(el=>el.textContent),
    navigation:['navA','navB','navB2','navC','navD'].reduce((result,id)=>{result[id]=document.getElementById(id).getAttribute('d');return result;},{}),
    zoom:['zoomTitle1','zoomRoom1Left','zoomRoom1Right','zoomMarker1','zoomTitle2','zoomRoom2Left','zoomRoom2Right','zoomMarker2'].map(id=>document.getElementById(id)?.textContent||'')
  };
})();

function applyFloorVisual(floor){
  const data=floorVisualData[floor];
  const rooms=[...document.querySelectorAll('.room')];
  const zoneTitles=[...document.querySelectorAll('.zone-title text')];
  const corridorLabels=[...document.querySelectorAll('.corridor-overlay-layer .corridor-label')];
  const zoomIds=['zoomTitle1','zoomRoom1Left','zoomRoom1Right','zoomMarker1','zoomTitle2','zoomRoom2Left','zoomRoom2Right','zoomMarker2'];

  if(!data){
    rooms.forEach((room,index)=>{
      const base=baseFloorVisual.rooms[index];
      const rect=room.querySelector('rect');
      const text=room.querySelector('text');
      ['x','y','width','height'].forEach((name,i)=>rect.setAttribute(name,base.rect[i]));
      text.setAttribute('x',base.text[0]);text.setAttribute('y',base.text[1]);
    });
    zoneTitles.forEach((el,index)=>el.textContent=baseFloorVisual.zoneTitles[index]);
    corridorLabels.forEach((el,index)=>el.textContent=baseFloorVisual.corridorLabels[index]);
    Object.entries(baseFloorVisual.navigation).forEach(([id,path])=>document.getElementById(id).setAttribute('d',path));
    zoomIds.forEach((id,index)=>{const el=document.getElementById(id);if(el)el.textContent=baseFloorVisual.zoom[index];});
    return;
  }

  rooms.forEach((room,index)=>{
    const layout=data.rooms[index];
    if(!layout) return;
    const rect=room.querySelector('rect');
    const text=room.querySelector('text');
    rect.setAttribute('x',layout[0]);rect.setAttribute('y',layout[1]);rect.setAttribute('width',layout[2]);rect.setAttribute('height',layout[3]);
    text.setAttribute('x',layout[4]);text.setAttribute('y',layout[5]);
  });
  zoneTitles.forEach((el,index)=>{if(data.zoneTitles[index])el.textContent=data.zoneTitles[index];});
  corridorLabels.forEach((el,index)=>{if(data.corridorLabels[index])el.textContent=data.corridorLabels[index];});
  Object.entries(data.navigation).forEach(([id,path])=>document.getElementById(id).setAttribute('d',path));
  zoomIds.forEach((id,index)=>{const el=document.getElementById(id);if(el&&data.zoom[index])el.textContent=data.zoom[index];});
}

function setFloor(floor){
  currentFloor = Number(floor);
  const data = floorData[currentFloor];
  document.getElementById('floorTitle').textContent = data.title;
  const missionTarget = document.getElementById('missionTargetText');
  if(missionTarget) missionTarget.textContent = data.target;
  const targetZone = document.getElementById('eventPosText');
  if(targetZone) targetZone.textContent = data.suspected;
  const riskZone = document.getElementById('riskZoneText');
  if(riskZone) riskZone.textContent = data.suspected;
  applyFloorVisual(currentFloor);
  resetNavigationRuntime();
  document.querySelectorAll('.room').forEach((room, index) => {
    const text = room.querySelector('text');
    if(text) text.textContent = data.rooms[index] || text.textContent;
  });
  document.getElementById('taskA').textContent = data.tasks[0];
  document.getElementById('taskB').textContent = data.tasks[1];
  document.getElementById('taskC').textContent = data.tasks[2];
  document.querySelectorAll('#floorButtons button').forEach(btn=>btn.classList.toggle('active', Number(btn.dataset.floor)===currentFloor));
  saveViewState();
  const stage = document.querySelector('.map-stage');
  stage.classList.remove('floor-transition');
  void stage.offsetWidth;
  stage.classList.add('floor-transition');
  animationStart=performance.now();
  scenarioPlan=null;
  delete robotHeadingState.robotD1;
  delete robotHeadingState.robotD2;
  if(currentFloor===2){
    restartScenario();
  }else{
    scenarioPhase=-1;
    resetScenarioVisuals();
    setText('missionTitleText','日常巡检运行中');
    setText('missionTargetText',`${data.title} 全区域巡检`);
    setText('missionSystemText','巡检链路正常 · 未发现异常');
    setText('dispatchState','协同均衡');
    setText('cooperationMode','常规分区巡检');
    setText('eventTypeText','暂无异常');
    setText('eventLevelText','正常');
    setText('eventPosText','—');
    setText('eventLinkText','—');
  }
}

function updateLatency(){
  const latency = 24 + Math.floor(Math.random() * 9);
  document.getElementById('latency').textContent = `${latency} ms`;
}



function getClientSnapshot(){
  const tasks=['A','B','C','D'].map(group=>({
    task_id:`floor-${currentFloor}-${group}`,
    area:group,
    floor:currentFloor,
    description:document.getElementById('task'+group)?.textContent||'',
    status:document.getElementById('status'+group)?.textContent||''
  }));
  const robots=robotConfig.map(cfg=>{
    const robotElement=document.getElementById(cfg.robot);
    const hasPosition=Boolean(robotElement?.getAttribute('transform'));
    return {
      robot_id:cfg.robot,
      name:document.querySelector(`#${cfg.robot} .robot-tag text`)?.textContent||cfg.robot,
      status:document.getElementById('status'+cfg.group)?.textContent||'',
      position:hasPosition?readRobotPosition(cfg.robot):null,
      area:cfg.group,
      task:document.getElementById('task'+cfg.group)?.textContent||'',
      online:true,
      last_update:new Date().toISOString()
    };
  });
  const eventType=document.getElementById('eventTypeText')?.textContent||'';
  const events=eventType&&eventType!=='暂无异常'?[{
    event_id:'current-floor-event',
    type:eventType,
    level:document.getElementById('eventLevelText')?.textContent||'',
    position:document.getElementById('eventPosText')?.textContent||'',
    status:document.getElementById('eventLinkText')?.textContent||''
  }]:[];
  return {
    system:{floor:currentFloor,status:document.getElementById('missionSystemText')?.textContent||''},
    robots,
    tasks,
    events,
    map:{floor:currentFloor,title:floorData[currentFloor].title},
    statistics:{group_progress:Object.assign({},groupProgress)}
  };
}

function applyServiceState(state,options={}){
  const floor=Number(state.map?.floor ?? state.system?.floor);
  if(options.fromCache && [1,2,3].includes(floor) && floor!==currentFloor) setFloor(floor);

  if(state.system){
    const statusText=state.system.status_text||state.system.status;
    if(statusText) setText('missionSystemText',statusText);
  }

  if(Array.isArray(state.tasks) && state.tasks.length){
    state.tasks.forEach(task=>{
      const area=String(task.area||'').toUpperCase();
      const title=task.title||task.description||task.task;
      if(['A','B','C','D'].includes(area) && title) setText('task'+area,title);
    });
  }

  if(Array.isArray(state.robots) && !options.fromCache){
    state.robots.forEach(robot=>{
      const id=robot.robot_id||robot.id;
      const x=Number(robot.position?.x);
      const y=Number(robot.position?.y);
      if(!id||!Number.isFinite(x)||!Number.isFinite(y)||(x===0&&y===0)) return;
      remoteRobotState.set(id,{position:{x,y},heading:robot.heading,receivedAt:performance.now()});
    });
  }

  if(state.events){
    const event=Array.isArray(state.events)?state.events[0]:state.events;
    if(event){
      if(event.type||event.event_type) setText('eventTypeText',event.type||event.event_type);
      if(event.level) setText('eventLevelText',event.level);
      if(event.position||event.location) setText('eventPosText',event.position||event.location);
      if(event.status||event.link_status) setText('eventLinkText',event.status||event.link_status);
    }
  }

  const progress=state.statistics?.group_progress;
  if(progress && typeof progress==='object'){
    ['A','B','C','D'].forEach(group=>{
      const value=Number(progress[group]);
      if(Number.isFinite(value)) groupProgress[group]=Math.max(0,Math.min(1,value));
    });
    updateLiveUi();
  }
}

function applyRealtimeMessage(message,resolvedValue){
  if(message.type==='robot_update'){
    const updates=Array.isArray(resolvedValue)?resolvedValue:[message.data];
    applyServiceState({robots:updates},{fromCache:false});
  }else if(message.type==='task_update'){
    applyServiceState({tasks:Array.isArray(resolvedValue)?resolvedValue:[message.data]},{fromCache:false});
  }else if(message.type==='event_update'){
    applyServiceState({events:Array.isArray(resolvedValue)?resolvedValue:[message.data]},{fromCache:false});
  }else if(message.type==='system_update'){
    applyServiceState({system:message.data},{fromCache:false});
  }
}

window.SearchClientBridge={getClientSnapshot,applyServiceState,applyRealtimeMessage};

window.addEventListener('resize', resizeScreen);
document.querySelectorAll('#floorButtons button').forEach(btn=>btn.addEventListener('click', ()=>setFloor(btn.dataset.floor)));
restoreViewState();
initZoomControls();
resizeScreen();
updateClock();
updateLatency();
setInterval(updateClock,1000);
setInterval(updateLatency,2200);
setFloor(currentFloor || 2);
requestAnimationFrame(moveRobots);


function initZoomControls(){
  const viewport = document.getElementById('viewport');
  const zoomInBtn = document.getElementById('zoomInBtn');
  const zoomOutBtn = document.getElementById('zoomOutBtn');
  const zoomResetBtn = document.getElementById('zoomResetBtn');

  zoomInBtn?.addEventListener('click', ()=>setUserZoom(userZoom * 1.2));
  zoomOutBtn?.addEventListener('click', ()=>setUserZoom(userZoom / 1.2));
  zoomResetBtn?.addEventListener('click', resetView);

  viewport.addEventListener('wheel', (event)=>{
    event.preventDefault();
    const factor = event.deltaY < 0 ? 1.12 : 1 / 1.12;
    setUserZoom(userZoom * factor, event.clientX, event.clientY);
  }, { passive:false });

  viewport.addEventListener('mousedown', (event)=>{
    if(event.button !== 0) return;
    dragState = { x:event.clientX, y:event.clientY };
    viewport.classList.add('dragging');
  });

  window.addEventListener('mousemove', (event)=>{
    if(!dragState) return;
    panX += event.clientX - dragState.x;
    panY += event.clientY - dragState.y;
    dragState = { x:event.clientX, y:event.clientY };
    applyViewTransform();
  });

  window.addEventListener('mouseup', ()=>{
    dragState = null;
    viewport.classList.remove('dragging');
  });

  viewport.addEventListener('dblclick', resetView);
}

window.addEventListener('beforeunload', saveViewState);
document.addEventListener('visibilitychange', ()=>{ if(document.visibilityState==='hidden') saveViewState(); });
