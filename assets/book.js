(function(){
  var root=document.documentElement, body=document.body;
  // 主题
  try{var t=localStorage.getItem('book-theme'); if(t) root.dataset.theme=t;}catch(e){}
  function flip(){var d=root.dataset.theme==='dark'?'light':'dark';root.dataset.theme=d;
    try{localStorage.setItem('book-theme',d)}catch(e){}}
  var tb=document.getElementById('theme'); if(tb) tb.onclick=flip;
  // 侧栏
  var side=document.querySelector('.side'), mb=document.getElementById('menu');
  if(mb) mb.onclick=function(){side.classList.toggle('open')};
  side.addEventListener('click',function(e){ if(e.target.tagName==='A') side.classList.remove('open'); });
  // 当前章节高亮
  var links=[].slice.call(document.querySelectorAll('.side a[href^="#"]'));
  var map={}; links.forEach(function(a){map[decodeURIComponent(a.getAttribute('href').slice(1))]=a;});
  var heads=[].slice.call(document.querySelectorAll('.page h2[id],.page h3[id],.page h4[id]'));
  var cur=null;
  function spy(){
    var y=window.scrollY+130, best=null;
    for(var i=0;i<heads.length;i++){ if(heads[i].offsetTop<=y) best=heads[i]; else break; }
    if(best&&best!==cur){ cur=best;
      links.forEach(function(a){a.classList.remove('on')});
      var a=map[best.id]; if(a){a.classList.add('on');} }
  }
  window.addEventListener('scroll',spy,{passive:true}); spy();
  // 回到顶部
  var top=document.getElementById('top');
  window.addEventListener('scroll',function(){ top.style.display=window.scrollY>700?'block':'none'; },{passive:true});
  top.onclick=function(){window.scrollTo({top:0,behavior:'smooth'})};
  // 全文搜索
  var IDX=(window.SEARCH_INDEX||[]);
  var res=document.getElementById('res'), box=res.querySelector('.box'), q=document.getElementById('q');
  function esc(s){return s.replace(/[&<>]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;'}[c]})}
  function run(){
    var kw=q.value.trim().toLowerCase();
    if(kw.length<1){res.style.display='none';box.innerHTML='';return;}
    var hit=[], n=0;
    for(var i=0;i<IDX.length&&hit.length<60;i++){
      var s=IDX[i], p=s.x.toLowerCase().indexOf(kw);
      if(p>=0){
        var a=Math.max(0,p-30), b=Math.min(s.x.length,p+kw.length+70);
        hit.push('<div class="row" data-h="'+s.i+'"><b>'+esc(s.t)+'</b><span>'+
          (a>0?'…':'')+esc(s.x.slice(a,p))+'<mark>'+esc(s.x.substr(p,kw.length))+'</mark>'+
          esc(s.x.slice(p+kw.length,b))+(b<s.x.length?'…':'')+'</span></div>');
      }
    }
    box.innerHTML = hit.length? hit.join('') : '<div class="row">没有找到「'+esc(q.value)+'」</div>';
    res.style.display='block';
    [].forEach.call(box.querySelectorAll('.row[data-h]'),function(r){
      r.onclick=function(){ location.hash=r.dataset.h; res.style.display='none'; };
    });
  }
  var tm=null;
  q.addEventListener('input',function(){clearTimeout(tm);tm=setTimeout(run,140)});
  res.addEventListener('click',function(e){ if(e.target===res) res.style.display='none'; });
  document.addEventListener('keydown',function(e){
    if(e.key==='/'&&document.activeElement!==q){e.preventDefault();q.focus();}
    if(e.key==='Escape'){res.style.display='none';q.blur();}
  });
})();
