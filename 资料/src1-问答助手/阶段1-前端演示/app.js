// 行知旅行 MVP 应用逻辑
(function(){
  const KB = window.KB;
  const state = {
    g1Confirmed: false,
    events: [],       // 变更事件队列
    notifications: [],// 通知任务
    manualRecords: [] // 转人工留痕
  };

  // ---------- Tab 切换 ----------
  document.querySelectorAll('nav button').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('nav button').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById(btn.dataset.tab).classList.add('active');
    });
  });

  // ---------- 问答助手 ----------
  function simpleTokenize(s){ return (s||'').replace(/[^\u4e00-\u9fa5a-zA-Z0-9]/g,'').toLowerCase(); }

  function searchKB(query){
    const q = simpleTokenize(query);
    // 1. 精确 FAQ 匹配
    for(const f of KB.faq){
      if(q.includes(simpleTokenize(f.q)) || simpleTokenize(f.q).includes(q)){
        return { type:'faq', text: f.a };
      }
    }
    // 2. 关键词命中证据
    const keywords = ['遗漏','耗时','覆盖率','审核门','转人工','退款','改签','赔偿','权限','脱敏','留存','回执','版本','主键','影响面','通知','升级','口径','旅客','服务商'];
    const hits = [];
    for(const e of KB.evidence){
      let score = 0;
      for(const kw of keywords){
        if(q.includes(simpleTokenize(kw)) && e.text.includes(kw)) score++;
      }
      if(score > 0) hits.push({e, score});
    }
    hits.sort((a,b)=>b.score-a.score);
    if(hits.length > 0){
      const top = hits.slice(0,2);
      return {
        type:'evidence',
        text: top.map(h => '【'+h.e.id+' · '+h.e.role_name+'】'+h.e.text).join('\n')
      };
    }
    return { type:'fallback', text:'未能从知识库找到明确答案，建议转人工咨询行程协调员或运营经理。' };
  }

  function addMsg(role, text, src){
    const box = document.getElementById('chatBox');
    const div = document.createElement('div');
    div.className = 'msg ' + role;
    div.innerHTML = '<div class="bubble">'+text.replace(/\n/g,'<br>')+'</div>' + (src ? '<div class="src">'+src+'</div>' : '');
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
  }

  window.ask = function(){
    const inp = document.getElementById('qaInput');
    const q = inp.value.trim();
    if(!q) return;
    addMsg('user', q);
    const r = searchKB(q);
    const src = r.type==='evidence' ? '来源：访谈证据库（36 条）' : (r.type==='faq' ? '来源：常见问题库' : '');
    addMsg('ai', r.text, src);
    inp.value = '';
  };
  window.quickAsk = function(q){
    document.getElementById('qaInput').value = q;
    window.ask();
  };

  // 欢迎语
  addMsg('ai', '你好，我是行知旅行问答助手。我可以基于 36 条访谈证据和知识库回答关于行程变更、通知闭环、审核门、权限等的问题。', '来源：系统');

  // ---------- 变更通知闭环 ----------
  window.registerEvent = function(){
    if(!state.g1Confirmed){
      alert('请先到「人工审核台」确认授权口径已签发（审核点1 · G1）。');
      document.querySelector('[data-tab="audit"]').click();
      return;
    }
    const type = document.getElementById('evtType').value;
    const tour = document.getElementById('evtTour').value.trim();
    const desc = document.getElementById('evtDesc').value.trim();
    if(!tour || !desc){ alert('请填写团号和事件描述'); return; }

    const evt = { id:'E'+Date.now(), type, tour, desc, time:new Date().toLocaleString(), status:'影响面已计算，待人工确认' };
    state.events.push(evt);

    // 模拟影响面计算
    const impact = ['订单：'+tour+' 的酒店/车队/游客名单','服务商：7 家（需分别确认资源可用）','影响对象：导游、协调员、服务商、旅客'];
    document.getElementById('impactResult').innerHTML =
      '<b>影响面计算结果（待审核点2人工确认）：</b><br>'+impact.join('<br>')+
      '<br><button class="btn" style="margin-top:10px" onclick="confirmImpact(\''+evt.id+'\')">人工确认建议并下发通知</button>';
  };

  window.confirmImpact = function(id){
    const evt = state.events.find(e=>e.id===id);
    if(!evt) return;
    evt.status = '通知已下发';
    state.notifications.push({
      evt, ackStatus:'待回执', ackDetail:''
    });
    renderNotify();
    document.getElementById('impactResult').innerHTML = '<span class="tag ok">已确认并下发通知</span> 事件 '+evt.type+'（'+evt.tour+'）通知已发送，等待服务商回执。';
  };

  window.confirmAck = function(idx){
    const n = state.notifications[idx];
    n.ackStatus = '已确认资源可用';
    n.ackDetail = '回执人：服务商 · '+new Date().toLocaleString();
    renderNotify();
  };

  function renderNotify(){
    const t = document.getElementById('notifyTable');
    if(state.notifications.length === 0){
      t.innerHTML = '<tr><th>事件</th><th>团号</th><th>状态</th><th>回执</th><th>操作</th></tr><tr><td colspan="5" class="hint">暂无通知任务</td></tr>';
      return;
    }
    let html = '<tr><th>事件</th><th>团号</th><th>状态</th><th>回执</th><th>操作</th></tr>';
    state.notifications.forEach((n,i)=>{
      html += '<tr><td>'+n.evt.type+'</td><td>'+n.evt.tour+'</td><td>'+n.evt.status+'</td><td>'+n.ackStatus+(n.ackDetail?'<br><span class="hint">'+n.ackDetail+'</span>':'')+'</td><td>'+
        (n.ackStatus==='待回执' ? '<button class="btn secondary" onclick="confirmAck('+i+')">确认回执</button>' : '<span class="tag ok">已闭环</span>')+
        '</td></tr>';
    });
    t.innerHTML = html;
  }

  // ---------- 人工审核台 ----------
  window.confirmG1 = function(){
    state.g1Confirmed = true;
    document.getElementById('g1Btn').disabled = true;
    document.getElementById('g1Status').innerHTML = ' · <span class="tag ok">已确认</span>';
  };

  window.submitManual = function(){
    const r = document.getElementById('auReason').value.trim();
    const o = document.getElementById('auOwner').value.trim();
    const t = document.getElementById('auTime').value.trim();
    const v = document.getElementById('auVer').value.trim();
    if(!r || !o || !t || !v){
      alert('转人工四要素必须全部填写（触发原因/接手人/确认时间/业务编号+版本）');
      return;
    }
    const rec = {reason:r, owner:o, time:t, ver:v, at:new Date().toLocaleString()};
    state.manualRecords.push(rec);
    document.getElementById('manualLog').innerHTML =
      '<span class="tag ok">已留痕</span> 转人工记录已保存：'+
      state.manualRecords.map(m=>m.owner+'（'+m.time+'）· '+m.reason+' · '+m.ver).join('<br>');
    document.getElementById('auReason').value=''; document.getElementById('auOwner').value='';
    document.getElementById('auTime').value=''; document.getElementById('auVer').value='';
  };
})();
