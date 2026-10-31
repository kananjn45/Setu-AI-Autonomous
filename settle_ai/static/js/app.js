/**
 * SETU — Autonomous Operations Teammate Client Engine
 * Handles real-time WebSockets, Soundbox MQTT audio, Sarvam Voice, and WhatsApp chat.
 */

let ws;
let isNetDropped = true;
let currentBillAmount = 400.0;
let currentDisputeIsFraud = false;

// --------------------------------------------------------------------------
// WebSocket Real-Time Connection
// --------------------------------------------------------------------------
function initWS() {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${proto}//${window.location.host}/ws/dispute-stream`);

  ws.onopen = () => {
    const ind = document.getElementById('ws-indicator');
    if (ind) {
      ind.textContent = '● Live Connected';
      ind.style.color = '#047857';
    }
  };

  ws.onmessage = (evt) => {
    try {
      const msg = JSON.parse(evt.data);
      handleStream(msg);
    } catch (e) {
      console.error('WS parse error:', e);
    }
  };

  ws.onclose = () => {
    const ind = document.getElementById('ws-indicator');
    if (ind) {
      ind.textContent = '○ Reconnecting...';
      ind.style.color = '#d97706';
    }
    setTimeout(initWS, 2000);
  };
}

function resetPipeline() {
  currentDisputeIsFraud = false;
  const nodes = ['node-ingest', 'node-diagnose_bank', 'node-diagnose_iot', 'node-diagnose_ledger', 'node-evaluate_risk', 'node-autonomous_settle'];
  nodes.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.className = 'pipeline-step';
  });
  const audioPill = document.getElementById('audio-pill');
  if (audioPill) audioPill.style.display = 'none';

  document.getElementById('desc-ingest').textContent = 'Understands speech in Hindi & regional languages. Finds reference number.';
  document.getElementById('desc-bank').textContent = 'Verifies if customer bank account was really debited.';
  document.getElementById('desc-iot').textContent = 'Checks cellular signal & battery to see if voice alert was missed.';
  document.getElementById('desc-ledger').textContent = 'Checks pending balances & prevents double payments.';
  document.getElementById('desc-risk').textContent = 'Ensures 95%+ confidence. Stops amounts above ₹5,000 for review.';
  document.getElementById('desc-settle').textContent = 'Credits shopkeeper balance, plays audio on speaker, and sends WhatsApp receipt.';
}

function addLog(actor, text) {
  const box = document.getElementById('op-log');
  if (!box) return;
  const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  const div = document.createElement('div');
  div.className = 'log-item';
  div.innerHTML = `<span class="time">${time}</span> <span class="actor">${actor}:</span> <span>${text}</span>`;
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
}

// --------------------------------------------------------------------------
// Stream Event Handler
// --------------------------------------------------------------------------
function handleStream(data) {
  if (data.event === 'NLU_START') {
    resetPipeline();
    addLog('Voice AI', `Listening to query: "${data.text}"`);
    document.getElementById('node-ingest').classList.add('active');
    document.getElementById('story-text').innerHTML = `<strong>Step 1:</strong> Listening to merchant query: <em>"${data.text}"</em>`;
  }
  else if (data.event === 'NLU_COMPLETE') {
    document.getElementById('node-ingest').classList.remove('active');
    document.getElementById('node-ingest').classList.add('completed');
    currentDisputeIsFraud = (data.entities.intent === 'PAYTM_SPOOF_FRAUD' || (data.entities.rrn && data.entities.rrn.startsWith('FAKE')));
    addLog('SETU', `Ref: ${data.entities.rrn} | Amount: ₹${data.entities.amount}`);
    document.getElementById('desc-ingest').textContent = `Understood: Ref ${data.entities.rrn} | Amount: ₹${data.entities.amount}`;
  }
  else if (data.event_type === 'NODE_EXECUTED') {
    const nodeName = data.node_name;
    const stepEl = document.getElementById(nodeName.replace('_', '-'));
    const isFraudStep = currentDisputeIsFraud || (data.step_summary && (data.step_summary.includes('NOT_FOUND') || data.step_summary.includes('Counterfeit') || data.step_summary.includes('ALERT_FAKE_PAYMENT')));

    if (isFraudStep) {
      currentDisputeIsFraud = true;
    }

    if (stepEl) {
      stepEl.classList.remove('active');
      if (isFraudStep && (nodeName === 'node_diagnose_bank' || nodeName === 'node_evaluate_risk' || nodeName === 'node_autonomous_settle')) {
        stepEl.classList.add('fraud-alert');
      } else if (data.step_summary && data.step_summary.includes('HALT')) {
        stepEl.classList.add('halted');
      } else {
        stepEl.classList.add('completed');
      }
      const lat = document.getElementById(`lat-${nodeName}`);
      if (lat) lat.textContent = `${data.latency_ms.toFixed(1)}ms`;
    }
    const friendlyNodeActors = {
      'node_ingest': 'Voice AI',
      'node_diagnose_bank': 'Bank Check',
      'node_diagnose_iot': 'Soundbox',
      'node_diagnose_ledger': 'Account Check',
      'node_evaluate_risk': 'Security',
      'node_autonomous_settle': 'Settlement'
    };
    const actorLabel = friendlyNodeActors[nodeName] || 'SETU';
    addLog(actorLabel, data.step_summary);

    if (nodeName === 'node_diagnose_bank') {
      if (currentDisputeIsFraud) {
        document.getElementById('desc-bank').innerHTML = `<span style="color:#ea2934; font-weight:800;">BANK CONFIRMED:</span> Zero money debited from customer!`;
        document.getElementById('story-text').innerHTML = `<strong>Step 2: Bank Check:</strong> <span style="color:#ea2934; font-weight:800;">ZERO MONEY DEBITED</span> at bank. This was a fake payment attempt!`;
      } else {
        document.getElementById('story-text').innerHTML = `<strong>Step 2: Bank Check:</strong> Bank confirms payment was debited from customer account successfully.`;
      }
    } else if (nodeName === 'node_diagnose_iot') {
      if (currentDisputeIsFraud) {
        document.getElementById('desc-iot').innerHTML = `<span style="color:#ea2934; font-weight:800;">SOUNDBOX SILENT:</span> No real transaction ever took place.`;
        document.getElementById('story-text').innerHTML = `<strong>Step 3: Soundbox Check:</strong> Speaker was silent because no real payment occurred!`;
      } else {
        document.getElementById('story-text').innerHTML = `<strong>Step 3: Soundbox Check:</strong> Soundbox signal was momentarily weak. Packet dropped in transit.`;
      }
    } else if (nodeName === 'node_evaluate_risk') {
      if (currentDisputeIsFraud) {
        document.getElementById('desc-risk').innerHTML = `<span style="color:#ea2934; font-weight:800;">FAKE PAY BLOCKED:</span> Counterfeit screenshot detected.`;
        document.getElementById('story-text').innerHTML = `<strong>Step 5: Fraud Defense:</strong> Counterfeit screen detected! Halting credit immediately to protect merchant.`;
      } else if (data.step_summary && data.step_summary.includes('HALT')) {
        document.getElementById('story-text').innerHTML = `<strong>Safety Limit:</strong> Amount is above ₹5,000. Paused for manager 1-click review.`;
      } else {
        document.getElementById('story-text').innerHTML = `<strong>Step 5: Safety Check:</strong> Payment verified safe (98% confidence). Proceeding to ring Soundbox!`;
      }
    } else if (nodeName === 'node_autonomous_settle') {
      if (currentDisputeIsFraud) {
        document.getElementById('desc-settle').innerHTML = `<span style="color:#ea2934; font-weight:800;">BLOCKED:</span> ₹0.00 released. Warning alarm played.`;
      }
    }
  }
  else if (data.event === 'RESOLUTION_FINALIZED') {
    const state = data.final_state;

    if (state.fraud_alert_triggered) {
      const settleEl = document.getElementById('node-autonomous_settle');
      if (settleEl) {
        settleEl.className = 'pipeline-step fraud-alert';
        document.getElementById('desc-settle').innerHTML = `<span style="color:#ea2934; font-weight:800;">FRAUD BLOCKED:</span> ₹0.00 released. Security alert sounded.`;
      }
      document.getElementById('sb-amount').textContent = 'FAKE PAYMENT';
      document.getElementById('sb-status').textContent = `SCAM BLOCKED (₹${state.amount.toFixed(2)} PREVENTED)`;
      document.getElementById('sb-led').className = 'led-circle alert';
      document.getElementById('story-text').innerHTML = `<strong>Fake Payment Blocked:</strong> Bank confirmed NO money was debited for Ref ${state.rrn}. Security warning sounded. Saved merchant ₹${state.amount.toFixed(2)}!`;
      addLog('Fraud Defense', `Blocked fake payment: Bank shows NO debit for Ref ${state.rrn}. Saved ₹${state.amount.toFixed(2)}.`);

      const waArea = document.getElementById('wa-messages-area');
      if (waArea) {
        const div = document.createElement('div');
        div.className = 'wa-bubble wa-bot';
        div.style.border = '1px solid #ef4444';
        div.style.background = '#fef2f2';
        div.innerHTML = `
          <div style="color:#b91c1c; font-weight:800; font-size:12px;">PAYTM FRAUD DEFENSE WARNING</div>
          <div style="font-size:11px; margin-top:4px; color:#991b1b; line-height:1.45;">
            <strong>Nakli Payment Pakda Gaya:</strong> Grahak ne ₹${state.amount.toFixed(2)} ka nakli Paytm Spoof screen dikhaya (Ref: ${state.rrn}). Bank par koi paisa debit nahi hua. Kripya samaan na dein!
          </div>
          <div class="wa-ts">${new Date().toLocaleTimeString()}</div>
        `;
        waArea.appendChild(div);
        waArea.scrollTop = waArea.scrollHeight;
      }

      if (data.soundbox_audio && data.soundbox_audio.audio_data_url) {
        playAudio(data.soundbox_audio.audio_data_url);
      }
      refreshBalances();
    } else if (state.hitl_required && !state.hitl_approved) {
      renderSupervisorCard(state);
      document.getElementById('sb-led').className = 'led-circle alert';
      document.getElementById('sb-status').textContent = 'Awaiting Manager Review';
      document.getElementById('story-text').innerHTML = `<strong>Safety Limit Active:</strong> ${state.hitl_reason}<br>Please review the Manager Desk below and click <strong>Approve &amp; Settle</strong> or <strong>Reject Claim</strong>.`;
    } else {
      document.getElementById('sb-amount').textContent = `₹${state.amount.toFixed(2)}`;
      document.getElementById('sb-status').textContent = 'Payment Verified & Reconciled';
      document.getElementById('sb-led').className = 'led-circle';

      const waArea = document.getElementById('wa-messages-area');
      if (waArea) {
        const div = document.createElement('div');
        div.className = 'wa-bubble wa-bot';
        div.innerHTML = `
          <div><strong>Payment Verified &amp; Added to Balance</strong></div>
          <div style="font-size:11px; margin-top:2px;">₹${state.amount.toFixed(2)} (Ref: ${state.rrn}) has been added to your settlement account. Soundbox confirmed.</div>
          <div class="wa-ts">${new Date().toLocaleTimeString()}</div>
        `;
        waArea.appendChild(div);
        waArea.scrollTop = waArea.scrollHeight;
      }

      document.getElementById('story-text').innerHTML = `<strong>Resolved in &lt; 1 second:</strong> Soundbox audio alert played and shopkeeper account credited.`;

      if (data.soundbox_audio && data.soundbox_audio.audio_data_url) {
        playAudio(data.soundbox_audio.audio_data_url);
      }
      refreshBalances();
    }
  }
  else if (data.event === 'HITL_APPROVED_FINAL') {
    const state = data.final_state;
    const hitlContainer = document.getElementById('hitl-container');
    if (hitlContainer) {
      hitlContainer.innerHTML = `
        <div style="background:#e6f7f3; border:1px solid #00b386; border-radius:12px; padding:16px; text-align:center; color:#005c45; font-size:13px;">
          <strong>Manager Approval Completed!</strong><br>
          Payment <strong>${state.dispute_id}</strong> (₹${state.amount.toFixed(2)}) approved and credited to merchant account.
        </div>
      `;
    }
    document.getElementById('sb-amount').textContent = `₹${state.amount.toFixed(2)}`;
    document.getElementById('sb-status').textContent = 'Manager Approved & Settled';
    document.getElementById('sb-led').className = 'led-circle';
    document.getElementById('story-text').innerHTML = `<strong>Manager Approved:</strong> ₹${state.amount.toFixed(2)} credited to merchant balance.`;

    addLog('Manager', `1-Click Approval executed. ₹${state.amount.toFixed(2)} credited to merchant balance.`);

    if (data.soundbox_audio && data.soundbox_audio.audio_data_url) {
      playAudio(data.soundbox_audio.audio_data_url);
    }
    refreshBalances();
  }
  else if (data.event === 'HITL_REJECTED_FINAL') {
    const state = data.final_state;
    const hitlContainer = document.getElementById('hitl-container');
    if (hitlContainer) {
      hitlContainer.innerHTML = `
        <div style="background:#fff1f2; border:1px solid #fecdd3; border-radius:12px; padding:16px; text-align:center; color:#9f1239; font-size:13px;">
          <div style="font-weight:800; font-size:14px; color:#be123c; margin-bottom:4px;">Claim Rejected by Manager</div>
          Claim for ₹${state.amount.toFixed(2)} denied.<br>
          <span style="font-size:12px; color:#e11d48; font-weight:600;">Zero funds released. Recorded in compliance log.</span>
        </div>
      `;
    }
    document.getElementById('sb-amount').textContent = `₹${state.amount.toFixed(2)}`;
    document.getElementById('sb-status').textContent = 'CLAIM REJECTED BY MANAGER';
    document.getElementById('sb-led').className = 'led-circle alert';
    document.getElementById('story-text').innerHTML = `<strong>Manager Rejected Claim:</strong> ₹${state.amount.toFixed(2)} order denied after checking bank records. Zero money released.`;

    const waArea = document.getElementById('wa-messages-area');
    if (waArea) {
      const div = document.createElement('div');
      div.className = 'wa-bubble wa-bot';
      div.style.border = '1px solid #fecdd3';
      div.style.background = '#fff1f2';
      div.innerHTML = `
        <div style="color:#be123c; font-weight:800; font-size:12px;">PAYTM NOTICE — CLAIM REJECTED</div>
        <div style="font-size:11px; margin-top:4px; color:#9f1239;">
          Dispute for <strong>₹${state.amount.toFixed(2)}</strong> (Ref ${state.rrn}) was reviewed by Manager and <strong>REJECTED</strong>.<br>
          <em>Note:</em> Zero balance credited.
        </div>
        <div class="wa-ts">${new Date().toLocaleTimeString()}</div>
      `;
      waArea.appendChild(div);
      waArea.scrollTop = waArea.scrollHeight;
    }

    addLog('Manager', `Claim for ₹${state.amount.toFixed(2)} REJECTED by Manager. Zero funds credited.`);
    refreshBalances();
  }
}

// --------------------------------------------------------------------------
// Manager 1-Click Review Desk
// --------------------------------------------------------------------------
function renderSupervisorCard(state) {
  const container = document.getElementById('hitl-container');
  if (!container) return;
  const currentDisputeAmt = state.amount || 15000.0;
  const currentDisputeRrn = state.rrn || '883920194821';
  container.innerHTML = `
    <div class="manager-review-box">
      <div class="manager-review-top">
        <div class="manager-review-title">Manager 1-Click Review Desk</div>
        <span class="manager-review-pill">Review Required</span>
      </div>
      <div class="manager-reason-box">
        <strong>${state.hitl_reason}</strong>
      </div>
      <div class="dossier-4col-grid">
        <div class="dossier-cell"><span class="label">Reference No</span><div class="value">${state.rrn}</div></div>
        <div class="dossier-cell"><span class="label">Order Amount</span><div class="value" style="color:var(--paytm-navy);">₹${currentDisputeAmt.toFixed(2)}</div></div>
        <div class="dossier-cell"><span class="label">Bank Check</span><div class="value" style="color:var(--paytm-green);">● ${state.bank_status || 'SUCCESS'}</div></div>
        <div class="dossier-cell"><span class="label">Soundbox Signal</span><div class="value">${state.soundbox_telemetry ? state.soundbox_telemetry.rssi_dbm : -88} dBm</div></div>
      </div>
      <div class="review-action-btns">
        <button type="button" class="btn-approve-clean" onclick="approveSupervisor('${state.dispute_id}', ${currentDisputeAmt}, '${currentDisputeRrn}')">
          Approve &amp; Settle (₹${currentDisputeAmt.toFixed(0)})
        </button>
        <button type="button" class="btn-reject-clean" onclick="rejectSupervisor('${state.dispute_id}', ${currentDisputeAmt}, '${currentDisputeRrn}')">
          Reject Claim
        </button>
      </div>
    </div>
  `;
}

async function approveSupervisor(disputeId, amount, rrn) {
  const amt = amount || 15000.0;
  const ref = rrn || '883920194821';
  const notes = 'Approved via Paytm Operations Manager Desk after checking bank clearing records.';
  
  handleStream({
    event: 'HITL_APPROVED_FINAL',
    final_state: { dispute_id: disputeId, amount: amt, rrn: ref, hitl_approved: true, is_completed: true }
  });

  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({
      action: 'APPROVE_HITL',
      dispute_id: disputeId,
      supervisor_notes: notes,
    }));
  }

  try {
    const res = await fetch('/api/dispute/approve-hitl', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dispute_id: disputeId, supervisor_notes: notes })
    });
    const data = await res.json();
    if (data.soundbox_audio && data.soundbox_audio.audio_data_url) {
      playAudio(data.soundbox_audio.audio_data_url);
    }
  } catch (err) {
    console.warn('REST approve fallback:', err);
  }
  refreshBalances();
}

async function rejectSupervisor(disputeId, amount, rrn) {
  const amt = amount || 15000.0;
  const ref = rrn || '883920194821';
  const notes = 'Dispute rejected by Manager after checking bank records.';
  
  handleStream({
    event: 'HITL_REJECTED_FINAL',
    final_state: { dispute_id: disputeId, amount: amt, rrn: ref, hitl_approved: false, is_completed: true }
  });

  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({
      action: 'REJECT_HITL',
      dispute_id: disputeId,
      supervisor_notes: notes,
    }));
  }

  try {
    await fetch('/api/dispute/reject-hitl', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dispute_id: disputeId, supervisor_notes: notes })
    });
  } catch (err) {
    console.warn('REST reject fallback:', err);
  }
  refreshBalances();
}

// --------------------------------------------------------------------------
// Audio Player
// --------------------------------------------------------------------------
function playAudio(dataUrl) {
  const pill = document.getElementById('audio-pill');
  const player = document.getElementById('audio-player');
  if (pill && player) {
    pill.style.display = 'flex';
    player.src = dataUrl;
    player.load();
    const p = player.play();
    if (p !== undefined) {
      p.catch(e => {
        console.log('Autoplay deferred:', e);
        addLog('Soundbox', 'Audio chime generated. Autoplay paused by browser policy.');
      });
    }
  }
}

// --------------------------------------------------------------------------
// --------------------------------------------------------------------------
// Real-Time WebSocket & Seamless Cloud Simulation Fallback
// --------------------------------------------------------------------------
function sendOrSimulate(payload) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(payload));
  } else {
    runClientSimulation(payload);
  }
}

function runClientSimulation(payload) {
  if (payload.action === 'APPROVE_HITL') {
    handleStream({
      event: 'HITL_APPROVED_FINAL',
      final_state: { dispute_id: payload.dispute_id, amount: payload.amount || 15000.0, rrn: payload.rrn || '883920194821', hitl_approved: true, is_completed: true },
      soundbox_audio: { audio_data_url: '/static/audio/chirp_883920194821.wav' }
    });
    return;
  }
  if (payload.action === 'REJECT_HITL') {
    handleStream({
      event: 'HITL_REJECTED_FINAL',
      final_state: { dispute_id: payload.dispute_id, amount: payload.amount || 15000.0, rrn: payload.rrn || '883920194821', hitl_approved: false, is_completed: true }
    });
    return;
  }

  // RUN_DISPUTE simulation
  const query = payload.query_text || '';
  let amt = payload.amount_override || currentBillAmount || 400.0;
  let rrn = payload.rrn_override || ('4102' + Math.floor(10000000 + Math.random() * 90000000));
  let isFraud = currentDisputeIsFraud || query.toLowerCase().includes('nakli') || query.toLowerCase().includes('fake') || query.toLowerCase().includes('spoof') || rrn.startsWith('FAKE');
  let isHighValue = amt >= 5000;

  const numMatch = query.match(/(\d+[\d,.]*)/);
  if (numMatch && !payload.amount_override) {
    const p = parseFloat(numMatch[1].replace(/,/g, ''));
    if (!isNaN(p) && p > 0) {
      amt = p;
      isHighValue = amt >= 5000;
    }
  }

  handleStream({ event: 'NLU_START', text: query });
  
  setTimeout(() => {
    handleStream({
      event: 'NLU_COMPLETE',
      entities: { rrn: rrn, amount: amt, intent: isFraud ? 'PAYTM_SPOOF_FRAUD' : (isHighValue ? 'HIGH_VALUE_DISPUTE' : 'SOUNDBOX_NOT_CONFIRMED'), source: 'sarvam_nlu' }
    });
  }, 120);

  setTimeout(() => {
    handleStream({
      node: 'node_ingest',
      status: 'COMPLETED',
      step_summary: `SARVAM Indic NLU: Processed shopkeeper speech. Extracted RRN ${rrn} & ₹${amt.toFixed(2)}.`,
      dispute_id: 'DSP_' + Date.now(),
      state: { rrn, amount: amt }
    });
  }, 260);

  setTimeout(() => {
    handleStream({
      node: 'node_diagnose_bank',
      status: 'COMPLETED',
      step_summary: isFraud
        ? `NPCI Switch Audit: ZERO DEBIT RECORD (U30 Not Found). No customer funds moved.`
        : `NPCI Switch Audit: SUCCESS (00 Approved). Payer: HDFC Bank. Bank confirms debit.`,
      dispute_id: 'DSP_' + Date.now(),
      state: { rrn, amount: amt, bank_status: isFraud ? 'NOT_FOUND' : 'SUCCESS' }
    });
  }, 420);

  setTimeout(() => {
    handleStream({
      node: 'node_diagnose_iot',
      status: 'COMPLETED',
      step_summary: `Soundbox IoT MQTT: Cellular RSSI -88dBm, Battery 84%. Volume set to 100%. Packet dropped diagnosed.`,
      dispute_id: 'DSP_' + Date.now(),
      state: { rrn, amount: amt, soundbox_status: 'PACKET_DROPPED' }
    });
  }, 580);

  setTimeout(() => {
    handleStream({
      node: 'node_diagnose_ledger',
      status: 'COMPLETED',
      step_summary: `Core Settlement Ledger: Status UNCREDITED. Reconciled canonical state: ${isFraud ? 'NOT_FOUND' : 'CREDITED'}.`,
      dispute_id: 'DSP_' + Date.now(),
      state: { rrn, amount: amt, canonical_state: isFraud ? 'NOT_FOUND' : 'CREDITED' }
    });
  }, 740);

  setTimeout(() => {
    handleStream({
      node: 'node_evaluate_risk',
      status: isHighValue ? 'HALTED_HITL' : 'COMPLETED',
      step_summary: isHighValue
        ? `Safety Circuit Breaker: ₹${amt.toFixed(2)} exceeds ₹5,000 threshold. Escaping to Manager Desk.`
        : (isFraud ? `Risk Circuit Breaker: FAKE PAYMENT INTERCEPTED. Zero ledger release.` : `Risk Circuit Breaker: 98.4% Confidence Score. Cleared for autonomous resolution.`),
      dispute_id: 'DSP_' + Date.now(),
      state: { rrn, amount: amt, hitl_required: isHighValue, hitl_reason: isHighValue ? `High-Value Order of ₹${amt.toFixed(2)} exceeds safety limit.` : null }
    });
  }, 900);

  setTimeout(() => {
    if (isHighValue) {
      handleStream({
        event: 'HITL_HALTED',
        dispute_id: 'DSP_' + Date.now(),
        state: {
          dispute_id: 'DSP_' + Date.now(),
          rrn: rrn,
          amount: amt,
          hitl_required: true,
          hitl_approved: false,
          hitl_reason: `High-Value Order of ₹${amt.toFixed(2)} exceeds ₹5,000 safety limit. Operations Manager review required.`,
          soundbox_telemetry: { rssi_dbm: -88, battery_percentage: 84 }
        }
      });
    } else if (isFraud) {
      handleStream({
        event: 'RESOLUTION_FINALIZED',
        dispute_id: 'DSP_' + Date.now(),
        final_state: {
          dispute_id: 'DSP_' + Date.now(),
          rrn: rrn,
          amount: amt,
          fraud_alert_triggered: true,
          is_completed: true,
          soundbox_pushed: true,
          ledger_credited: false
        },
        soundbox_audio: {
          audio_data_url: '/static/audio/chirp_security_warning.wav',
          is_fraud_alarm: true,
          text: '🚨 Saavdhan! Yeh ek fraud transaction hai. Samaan na dein. Paytm par koi paisa prapt nahi hua hai.'
        }
      });
    } else {
      handleStream({
        event: 'RESOLUTION_FINALIZED',
        dispute_id: 'DSP_' + Date.now(),
        final_state: {
          dispute_id: 'DSP_' + Date.now(),
          rrn: rrn,
          amount: amt,
          fraud_alert_triggered: false,
          is_completed: true,
          soundbox_pushed: true,
          ledger_credited: true
        },
        soundbox_audio: {
          audio_data_url: '/static/audio/chirp_410294820192.wav',
          text: `Paytm par ${Math.round(amt)} rupaye prapt hue`
        }
      });
    }
  }, 1080);
}


// Scenario & Custom Query Triggers
// --------------------------------------------------------------------------
function runPreset(type) {
  let payload;
  if (type === '350_drop') {
    const amt = currentBillAmount > 0 ? currentBillAmount : 400.0;
    payload = {
      action: 'RUN_DISPUTE',
      query_text: `Bhaiya humari dukan pe ${Math.round(amt)} rupaye kata par Soundbox nahi bola. RRN number hai 410294820192`,
      amount_override: amt,
      rrn_override: '410294820192',
    };
  } else if (type === '15000_hitl') {
    payload = {
      action: 'RUN_DISPUTE',
      query_text: 'Sharma Kirana Store ka 15,000 rupaye ruka hua hai RRN 883920194821',
      amount_override: 15000.0,
      rrn_override: '883920194821',
    };
  } else if (type === '420_reversal') {
    payload = {
      action: 'RUN_DISPUTE',
      query_text: 'Customer bol raha hai 420 rupaye kat gaye RRN 772910394812',
      amount_override: 420.0,
      rrn_override: '772910394812',
    };
  } else if (type === 'spoof_scam') {
    const amt = currentBillAmount > 0 ? currentBillAmount : 400.0;
    const fakeRrn = 'FAKE_' + Math.floor(100000 + Math.random() * 900000);
    currentDisputeIsFraud = true;
    payload = {
      action: 'RUN_DISPUTE',
      query_text: `Customer bol raha hai ₹${Math.round(amt)} pay kar diya aur nakli screen dikhaya RRN ${fakeRrn}`,
      amount_override: amt,
      rrn_override: fakeRrn,
    };
  }
  sendOrSimulate(payload);
}

function submitCustomQuery() {
  const text = document.getElementById('query-input').value.trim();
  if (!text) {
    alert('Please enter a shopkeeper query in Hindi or English.');
    return;
  }
  sendOrSimulate({ action: 'RUN_DISPUTE', query_text: text });
}

async function triggerTeammateMission(missionId) {
  document.querySelectorAll('.mission-tab').forEach(t => t.classList.remove('active'));

  if (missionId === 'SERVICE_DISPUTE') {
    const tab = document.getElementById('tab-mission1'); if (tab) tab.classList.add('active');
    const amt = currentBillAmount > 0 ? currentBillAmount : 400.0;
    addLog('SETU', `Scenario 1: Silent Soundbox (₹${amt.toFixed(2)} Drop)...`);
    sendOrSimulate({
      action: 'RUN_DISPUTE',
      query_text: `Bhaiya humari dukan pe ${Math.round(amt)} rupaye kata par Soundbox nahi bola. RRN number hai 410294820192`,
      amount_override: amt,
      rrn_override: '410294820192'
    });
  } else if (missionId === 'FRAUD_SPOOF') {
    const tab = document.getElementById('tab-mission2'); if (tab) tab.classList.add('active');
    const amt = currentBillAmount > 0 ? currentBillAmount : 400.0;
    const fakeRrn = 'FAKE_' + Math.floor(100000 + Math.random() * 900000);
    currentDisputeIsFraud = true;
    addLog('SETU', `Scenario 2: Fake Payment App Intercepted for ₹${amt.toFixed(2)}...`);
    sendOrSimulate({
      action: 'RUN_DISPUTE',
      query_text: `Customer bol raha hai usne ₹${Math.round(amt)} pay kar diya aur screenshot dikhaya RRN ${fakeRrn}`,
      amount_override: amt,
      rrn_override: fakeRrn
    });
  } else if (missionId === 'SALES_UPGRADE') {
    const tab = document.getElementById('tab-mission3'); if (tab) tab.classList.add('active');
    addLog('SETU', 'Scenario 3: Soundbox Hardware Check & 4G Pro Upgrade Offer...');
    resetPipeline();
    document.getElementById('node-ingest').classList.add('completed');
    document.getElementById('node-diagnose_iot').classList.add('completed');
    document.getElementById('sb-status').textContent = 'Hardware Check: Weak 2G Signal Detected';
    document.getElementById('sb-amount').textContent = 'UPGRADE 4G PRO';
    document.getElementById('story-text').innerHTML = `<strong>Device Check Complete:</strong> Soundbox has old 2G cellular signal (-98dBm). Generated 1-Click Upgrade Offer to Paytm Soundbox 4G Pro at ₹199!`;
    addLog('Store Growth', 'Merchant Gupta Tea Stall diagnosed with old 2G signal drops. Offered Soundbox 4G Pro upgrade at ₹199.');

    const waArea = document.getElementById('wa-messages-area');
    if (waArea) {
      const div = document.createElement('div');
      div.className = 'wa-bubble wa-bot';
      div.innerHTML = `
        <div style="color:#7c3aed; font-weight:800; font-size:12px;">PAYTM BUSINESS DEVICE UPGRADE</div>
        <div style="font-size:11px; margin-top:4px;">Namaste Gupta ji! Aapke Soundbox 2G me mobile signal kamzor hai jisse awaz nahi aati.</div>
        <div style="background:#f5f3ff; border:1px solid #c4b5fd; border-radius:8px; padding:8px; margin-top:6px; font-size:11px;">
          <strong>Paytm Soundbox 4G Pro (Dual SIM + Louder Speaker)</strong><br>
          <span style="color:#6b21a8; font-weight:700;">Special Price: ₹199</span> (Save ₹300)
        </div>
        <div class="wa-ts">${new Date().toLocaleTimeString()}</div>
      `;
      waArea.appendChild(div);
      waArea.scrollTop = waArea.scrollHeight;
    }
  } else if (missionId === 'HITL_SUPERVISOR') {
    const tab = document.getElementById('tab-mission4'); if (tab) tab.classList.add('active');
    addLog('SETU', 'Scenario 4: Large Order Review (₹15,000)...');
    sendOrSimulate({
      action: 'RUN_DISPUTE',
      query_text: 'Sharma Kirana Store ka 15,000 rupaye ruka hua hai RRN 883920194821',
      amount_override: 15000.0,
      rrn_override: '883920194821'
    });
  } else if (missionId === 'PROACTIVE_FLEET') {
    const tab = document.getElementById('tab-mission5'); if (tab) tab.classList.add('active');
    addLog('SETU', 'Scenario 5: Bank Server Delay Notice...');
    resetPipeline();
    document.getElementById('node-diagnose_bank').classList.add('completed');
    document.getElementById('sb-status').textContent = 'BANK NOTICE: SBI DELAYS DETECTED';
    document.getElementById('sb-led').className = 'led-circle alert';
    document.getElementById('story-text').innerHTML = `<strong>Bank Slowdown Notice:</strong> Detected SBI server delay. Sent 1-line Hindi voice warning to 10,482 Soundboxes!`;
    addLog('Fleet Monitor', 'SBI UPI server slow (4,250ms). Spoke 1-line Hindi warning to 10,482 Soundboxes: "Dhyan dein: SBI server dheema hai..."');
    playAudio('/static/audio/chirp_switch_advisory.wav');
  }
}

// --------------------------------------------------------------------------
// Soundbox Hardware Network Simulator
// --------------------------------------------------------------------------
function toggleSoundboxNetwork() {
  isNetDropped = !isNetDropped;
  const badge = document.getElementById('sb-toggle-badge');
  const netText = document.getElementById('sb-net-text');
  const led = document.getElementById('sb-led');

  if (isNetDropped) {
    if (badge) { badge.textContent = 'Signal Weak'; badge.style.color = '#f59e0b'; }
    if (netText) netText.textContent = '4G (Weak)';
    if (led) led.className = 'led-circle alert';
    addLog('Soundbox', 'Simulated weak internet on Soundbox.');
  } else {
    if (badge) { badge.textContent = 'Strong Signal'; badge.style.color = '#10b981'; }
    if (netText) netText.textContent = '4G Signal';
    if (led) led.className = 'led-circle';
    addLog('Soundbox', 'Internet signal restored.');
  }
}

// --------------------------------------------------------------------------
// Balances & Currency Formatter
// --------------------------------------------------------------------------
async function refreshBalances() {
  try {
    const res = await fetch('/api/state');
    const data = await res.json();
    if (data.ledger_balances) {
      const gupta = data.ledger_balances['MERCH_GUPTA_TEA'] || 4820.50;
      const sharma = data.ledger_balances['MERCH_SHARMA_KIRANA'] || 12450.00;
      const bgEl = document.getElementById('bal-gupta');
      const bsEl = document.getElementById('bal-sharma');
      if (bgEl) bgEl.textContent = `₹${gupta.toLocaleString('en-IN', {minimumFractionDigits: 2})}`;
      if (bsEl) bsEl.textContent = `₹${sharma.toLocaleString('en-IN', {minimumFractionDigits: 2})}`;
    }
  } catch (e) {
    console.error('Error fetching balances:', e);
  }
}

function setBillAmount(amt) {
  currentBillAmount = parseFloat(amt) || 400.0;
  const inputEl = document.getElementById('qr-bill-amount');
  if (inputEl) inputEl.value = currentBillAmount;
  updateBillAmountDisplay(currentBillAmount);
}

function onBillAmountChange(val) {
  const parsed = parseFloat(val);
  if (!isNaN(parsed) && parsed > 0) {
    currentBillAmount = parsed;
    updateBillAmountDisplay(currentBillAmount);
  }
}

function updateBillAmountDisplay(amt) {
  const formatted = `₹${amt.toFixed(2)}`;
  const phoneDisplay = document.getElementById('phone-display-amount');
  if (phoneDisplay) phoneDisplay.textContent = formatted;

  const sbAmt = document.getElementById('sb-amount');
  if (sbAmt && !sbAmt.textContent.includes('SPOOF') && !sbAmt.textContent.includes('UPGRADE')) {
    sbAmt.textContent = formatted;
  }

  const payBtn = document.getElementById('btn-cust-pay');
  if (payBtn) payBtn.innerHTML = `Pay ${formatted} via UPI (Simulate Weak Internet)`;

  const fakeBtn = document.getElementById('btn-fake-pay');
  if (fakeBtn) fakeBtn.innerHTML = `Fake Payment Screen (${formatted})`;

  const m1Card = document.getElementById('mission1-amt-card');
  if (m1Card) m1Card.textContent = `Weak Internet Drop (${formatted})`;

  const m2Card = document.getElementById('mission2-amt-card');
  if (m2Card) m2Card.textContent = `Counterfeit Screen (${formatted})`;

  const presetSpoof = document.getElementById('preset-spoof-amt');
  if (presetSpoof) presetSpoof.textContent = formatted;

  document.querySelectorAll('.amount-chip').forEach(c => c.classList.remove('active'));
  const activeChip = document.getElementById(`chip-${Math.round(amt)}`);
  if (activeChip) activeChip.classList.add('active');
}

// --------------------------------------------------------------------------
// QR Modal & Customer UPI Simulation
// --------------------------------------------------------------------------
function openQrModal() {
  document.getElementById('qr-modal-overlay').style.display = 'flex';
  const alertBox = document.getElementById('phone-alert');
  if (alertBox) alertBox.style.display = 'none';
  const btn = document.getElementById('btn-cust-pay');
  if (btn) {
    btn.disabled = false;
    btn.innerHTML = `Pay ₹${currentBillAmount.toFixed(2)} via UPI (Simulate Weak Internet)`;
  }
  const fakeBtn = document.getElementById('btn-fake-pay');
  if (fakeBtn) {
    fakeBtn.innerHTML = `Fake Payment Screen (₹${currentBillAmount.toFixed(2)})`;
  }
}

function closeQrModal() {
  document.getElementById('qr-modal-overlay').style.display = 'none';
}

async function simulateCustomerPay() {
  const btn = document.getElementById('btn-cust-pay');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = 'Processing UPI Payment...';
  }
  const amt = currentBillAmount > 0 ? currentBillAmount : 400.0;

  try {
    const res = await fetch('/api/simulator/customer-pay', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ amount: amt })
    });
    const data = await res.json();
    
    const alertBox = document.getElementById('phone-alert');
    if (alertBox) {
      alertBox.style.display = 'flex';
      alertBox.style.flexDirection = 'column';
      alertBox.style.background = '#f0fdf4';
      alertBox.style.border = '1px solid #bbf7d0';
      alertBox.innerHTML = `
        <div style="font-weight:800; font-size:13px; color:#15803d;">₹${data.amount.toFixed(2)} Debited Successfully</div>
        <div style="font-size:12px; margin-top:3px;"><strong>Reference No:</strong> <span class="tabular-num">${data.rrn}</span></div>
        <div style="font-size:12px;"><strong>Bank:</strong> ${data.payer_bank} (Customer account debited)</div>
        <div style="margin-top:6px; color:#b91c1c; font-weight:700; font-size:12px;">
          Soundbox Alert: Weak internet drop! Soundbox remained silent.
        </div>
        <button onclick="applySimulatedGrievance('${data.suggested_query}', '${data.rrn}', ${data.amount})" style="margin-top:8px; background:var(--paytm-navy); color:#fff; border:none; border-radius:6px; padding:8px 12px; font-weight:800; font-size:12px; cursor:pointer;">
          Raise Shopkeeper Grievance for ₹${data.amount.toFixed(0)}
        </button>
      `;
    }

    isNetDropped = true;
    document.getElementById('sb-toggle-badge').textContent = 'Signal Weak';
    document.getElementById('sb-toggle-badge').style.color = '#f59e0b';
    document.getElementById('sb-net-text').textContent = '4G (Weak)';
    document.getElementById('sb-led').className = 'led-circle alert';
    document.getElementById('sb-status').textContent = 'Weak Signal (Missed Alert ' + data.rrn.slice(-4) + ')';
    
    addLog('Simulator', `Customer debited ₹${data.amount.toFixed(2)} (Ref: ...${data.rrn.slice(-4)}). Weak internet simulated.`);
  } catch (err) {
    alert('Simulation error: ' + err);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `Pay ₹${amt.toFixed(2)} via UPI (Simulate Weak Internet)`;
    }
  }
}

function simulateFakePay() {
  const amt = currentBillAmount > 0 ? currentBillAmount : 400.0;
  const fakeRrn = 'FAKE_' + Math.floor(100000 + Math.random() * 900000);
  currentDisputeIsFraud = true;

  const alertBox = document.getElementById('phone-alert');
  if (alertBox) {
    alertBox.style.display = 'flex';
    alertBox.style.flexDirection = 'column';
    alertBox.style.background = '#fef2f2';
    alertBox.style.border = '1.5px solid #ef4444';
    alertBox.innerHTML = `
      <div style="font-weight:800; font-size:13px; color:#b91c1c;">COUNTERFEIT PAYMENT SCREEN DETECTED</div>
      <div style="font-size:12px; margin-top:3px;"><strong>Fake Ref No:</strong> <span class="tabular-num" style="color:#991b1b;">${fakeRrn}</span></div>
      <div style="font-size:12px;"><strong>Amount Claimed:</strong> ₹${amt.toFixed(2)} (Fake App Screen)</div>
      <div style="margin-top:4px; font-size:12px; color:#7f1d1d; font-weight:600;">Bank Check: ZERO MONEY DEBITED. Stopping scam...</div>
    `;
  }

  setTimeout(() => {
    closeQrModal();
    addLog('Simulator', `Customer showed fake payment screen for ₹${amt.toFixed(2)} (Ref: ...${fakeRrn.slice(-4)}). SETU stopping scam...`);
    sendOrSimulate({
      action: 'RUN_DISPUTE',
      query_text: `Customer bol raha hai usne ₹${Math.round(amt)} pay kar diya nakli screenshot dikhaya RRN ${fakeRrn}`,
      amount_override: amt,
      rrn_override: fakeRrn
    });
  }, 500);
}

function applySimulatedGrievance(query, rrn, amount) {
  closeQrModal();
  document.getElementById('query-input').value = query;
  const inputEl = document.getElementById('query-input');
  inputEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
  inputEl.style.boxShadow = '0 0 0 3px #00baf2';
  setTimeout(() => { inputEl.style.boxShadow = ''; }, 1500);
  addLog('Store', `Issue ready for ₹${amount} (Ref ...${rrn.slice(-4)}). Click 'Fix Payment Dispute Now'.`);
}

function useSampleSpeech() {
  const amt = currentBillAmount || 400;
  document.getElementById('query-input').value = `Bhaiya humari dukan pe ${Math.round(amt)} rupaye kata par Soundbox nahi bola. RRN number hai 410294820192`;
  addLog('Sample Voice', `Sample query ready for ₹${Math.round(amt)}: "Bhaiya 400 rupaye kata par Soundbox nahi bola..."`);
}

function useSampleFakeSpeech() {
  const amt = currentBillAmount || 400;
  const fakeRrn = 'FAKE_' + Math.floor(100000 + Math.random() * 900000);
  document.getElementById('query-input').value = `Customer bol raha hai usne ₹${Math.round(amt)} pay kar diya aur nakli screen dikhaya RRN ${fakeRrn}`;
  addLog('Sample Voice', `Sample fake payment query ready for ₹${Math.round(amt)}.`);
}

let currentVoiceLang = 'hi-IN';
function selectVoiceLang(langCode, sampleText, btnEl) {
  currentVoiceLang = langCode;
  document.querySelectorAll('.lang-btn').forEach(c => c.classList.remove('active'));
  if (btnEl) btnEl.classList.add('active');
  if (sampleText) {
    document.getElementById('query-input').value = sampleText;
  }
  addLog('Language', `Switched language to ${langCode}. Voice recognition and speaker alert ready.`);
}

// --------------------------------------------------------------------------
// Microphone Web Audio Recording
// --------------------------------------------------------------------------
let audioCtx = null;
let micStream = null;
let scriptNode = null;
let pcmBuffers = [];
let isRecording = false;
let recTimerInterval = null;
let recSeconds = 0;

async function toggleMicRecording() {
  if (isRecording) {
    await stopMicRecording();
  } else {
    await startMicRecording();
  }
}

async function startMicRecording() {
  try {
    micStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
    audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
    const source = audioCtx.createMediaStreamSource(micStream);
    scriptNode = audioCtx.createScriptProcessor(4096, 1, 1);
    pcmBuffers = [];

    scriptNode.onaudioprocess = (e) => {
      if (!isRecording) return;
      const inputData = e.inputBuffer.getChannelData(0);
      pcmBuffers.push(new Float32Array(inputData));
    };

    source.connect(scriptNode);
    scriptNode.connect(audioCtx.destination);

    isRecording = true;
    recSeconds = 0;
    document.getElementById('recording-bar').style.display = 'flex';
    document.getElementById('btn-record-mic').style.background = '#fee2e2';
    document.getElementById('mic-icon').textContent = '⏹️';
    document.getElementById('mic-text').textContent = 'Stop Recording';

    recTimerInterval = setInterval(() => {
      recSeconds++;
      const m = String(Math.floor(recSeconds / 60)).padStart(2, '0');
      const s = String(recSeconds % 60).padStart(2, '0');
      document.getElementById('rec-timer').textContent = `${m}:${s}`;
    }, 1000);

    addLog('Voice AI', 'Microphone active. Listening to your query...');
  } catch (err) {
    alert('Microphone access denied: ' + err.message);
  }
}

async function stopMicRecording() {
  isRecording = false;
  clearInterval(recTimerInterval);
  document.getElementById('recording-bar').style.display = 'none';
  document.getElementById('btn-record-mic').style.background = '#ffffff';
  document.getElementById('mic-icon').textContent = '●';
  document.getElementById('mic-text').textContent = 'Speak via Live Mic';

  if (scriptNode) scriptNode.disconnect();
  if (micStream) micStream.getTracks().forEach(t => t.stop());
  if (audioCtx) await audioCtx.close();

  let totalLen = pcmBuffers.reduce((acc, b) => acc + b.length, 0);
  let merged = new Float32Array(totalLen);
  let offset = 0;
  for (let b of pcmBuffers) {
    merged.set(b, offset);
    offset += b.length;
  }

  let wavBuffer = encodeWAV(merged, 16000);
  let audioBlob = new Blob([wavBuffer], { type: 'audio/wav' });

  addLog('Voice AI', `Recorded ${(totalLen / 16000).toFixed(1)}s audio. Understanding query...`);

  let formData = new FormData();
  formData.append('audio_file', audioBlob, 'grievance.wav');
  formData.append('language_code', currentVoiceLang);

  try {
    const res = await fetch('/api/voice/grievance', {
      method: 'POST',
      body: formData,
    });
    const data = await res.json();
    if (data.transcript) {
      document.getElementById('query-input').value = data.transcript;
      addLog('Voice AI', `Understood: "${data.transcript}" (Amount: ₹${data.extracted_entities.amount})`);
      if (data.agent_state) {
        handleStream({ event: 'RESOLUTION_FINALIZED', final_state: data.agent_state, soundbox_audio: data.soundbox_audio });
      }
    }
  } catch (err) {
    addLog('Voice AI', 'Voice error: ' + err.message);
  }
}

function encodeWAV(samples, sampleRate) {
  let buffer = new ArrayBuffer(44 + samples.length * 2);
  let view = new DataView(buffer);
  function writeString(view, offset, string) {
    for (let i = 0; i < string.length; i++) {
      view.setUint8(offset + i, string.charCodeAt(i));
    }
  }
  writeString(view, 0, 'RIFF');
  view.setUint32(4, 36 + samples.length * 2, true);
  writeString(view, 8, 'WAVE');
  writeString(view, 12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeString(view, 36, 'data');
  view.setUint32(40, samples.length * 2, true);
  let offset = 44;
  for (let i = 0; i < samples.length; i++, offset += 2) {
    let s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
  }
  return buffer;
}

// --------------------------------------------------------------------------
// WhatsApp Messenger Simulator
// --------------------------------------------------------------------------
async function sendWhatsAppMessage(overrideText, amountHint, rrnHint) {
  const input = document.getElementById('wa-user-input');
  const text = overrideText || (input ? input.value.trim() : '');
  if (!text) return;
  if (input) input.value = '';

  const messagesArea = document.getElementById('wa-messages-area');
  const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  const userDiv = document.createElement('div');
  userDiv.className = 'wa-bubble wa-user';
  userDiv.innerHTML = `${text}<div class="wa-ts">${timeStr} ✓✓</div>`;
  messagesArea.appendChild(userDiv);
  messagesArea.scrollTop = messagesArea.scrollHeight;

  try {
    const res = await fetch('/api/whatsapp/message', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message_text: text,
        amount_hint: amountHint || null,
        rrn_hint: rrnHint || null,
      })
    });
    const data = await res.json();

    const botDiv = document.createElement('div');
    botDiv.className = 'wa-bubble wa-bot';

    if (data.fraud_detected || (data.agent_state && data.agent_state.fraud_alert_triggered)) {
      botDiv.style.border = '1px solid #ef4444';
      botDiv.style.background = '#fef2f2';
      botDiv.innerHTML = `
        <div style="color:#b91c1c; font-weight:800; font-size:12px;">PAYTM FRAUD DEFENSE WARNING</div>
        <div style="font-size:11px; margin-top:4px; color:#991b1b; line-height:1.45;">
          <strong>Nakli Payment Pakda Gaya:</strong> Grahak ne ₹${data.amount.toFixed(2)} ka nakli Paytm screen dikhaya (Ref: <code class="tabular-num">${data.rrn}</code>).<br>
          • <strong>Bank Check:</strong> <span style="font-weight:800; color:#dc2626;">ZERO MONEY DEBITED</span><br>
          • <strong>Account Impact:</strong> ₹0.00 Released (No money given)<br>
          • <strong>Soundbox Alert:</strong> Security Warning Chime Played<br>
          <div style="margin-top:6px; background:#fee2e2; border:1px solid #fca5a5; padding:6px 8px; border-radius:6px; color:#7f1d1d; font-weight:700;">
            Warning: Samaan na dein! This was a fake payment attempt.
          </div>
        </div>
        <div class="wa-ts">${timeStr}</div>
      `;
      document.getElementById('sb-amount').textContent = 'FAKE PAYMENT';
      document.getElementById('sb-status').textContent = `SCAM BLOCKED (₹${data.amount.toFixed(2)})`;
      document.getElementById('sb-led').className = 'led-circle alert';
      if (data.soundbox_audio && data.soundbox_audio.audio_data_url) {
        playAudio(data.soundbox_audio.audio_data_url);
      }
      addLog('WhatsApp', `Fraud Defense intercepted fake payment of ₹${data.amount.toFixed(2)}.`);
    } else if (data.is_settled && !data.hitl_tripped) {
      const shortHash = data.digital_receipt && data.digital_receipt.sha256_audit_seal
        ? data.digital_receipt.sha256_audit_seal.slice(0, 14) + '...'
        : 'SHA256-VERIFIED';

      botDiv.innerHTML = `
        <div><strong>Payment Verified &amp; Added to Balance</strong></div>
        <div style="font-size:11px; margin-top:2px; color:#374151;">Fixed in under 45 seconds automatically.</div>
        <div style="background:#f8fafc; border:1px solid #cbd5e1; border-radius:6px; padding:8px; margin-top:6px; font-size:11px;">
          <div><strong>Amount:</strong> <span class="tabular-num">₹${data.amount.toFixed(2)}</span></div>
          <div><strong>Reference No:</strong> <span class="tabular-num">${data.rrn}</span></div>
          <div><strong>Status:</strong> Added to Merchant Settlement Account</div>
          <div><strong>Digital Seal:</strong> <code class="tabular-num">${shortHash}</code></div>
        </div>
        <div class="wa-ts">${timeStr}</div>
      `;

      if (data.soundbox_audio && data.soundbox_audio.audio_data_url) {
        playAudio(data.soundbox_audio.audio_data_url);
      }
      document.getElementById('sb-amount').textContent = `₹${data.amount.toFixed(2)}`;
      document.getElementById('sb-status').textContent = 'WhatsApp Grievance Reconciled';
      document.getElementById('sb-led').className = 'led-circle';
      refreshBalances();
      addLog('WhatsApp', `Dispute settled via WhatsApp for ₹${data.amount.toFixed(2)}.`);
    } else {
      botDiv.innerHTML = `
        <div style="color:#b45309; font-weight:700;">Large Amount Manager Review</div>
        <div style="font-size:11px; margin-top:4px;">Dispute for <strong>₹${data.amount.toFixed(2)}</strong> (Ref: <span class="tabular-num">${data.rrn}</span>) is above the ₹5,000 safety limit.</div>
        <div style="font-size:11px; margin-top:4px; color:#4b5563;">An Operations Manager has received this on their desk for 1-click review.</div>
        <div class="wa-ts">${timeStr}</div>
      `;
      addLog('Manager Review', `Large amount grievance of ₹${data.amount.toFixed(2)} paused for manager review.`);
    }

    messagesArea.appendChild(botDiv);
    messagesArea.scrollTop = messagesArea.scrollHeight;
  } catch (err) {
    // Client-side fallback for static cloud hosting
    const botDiv = document.createElement('div');
    botDiv.className = 'wa-bubble wa-bot';
    const isFake = text.toLowerCase().includes('nakli') || text.toLowerCase().includes('fake') || text.toLowerCase().includes('spoof') || (rrnHint && rrnHint.startsWith('FAKE'));
    const amt = amountHint || 400.0;
    const rrn = rrnHint || '4102' + Math.floor(10000000 + Math.random() * 90000000);

    if (isFake) {
      botDiv.style.border = '1px solid #ef4444';
      botDiv.style.background = '#fef2f2';
      botDiv.innerHTML = `
        <div style="color:#b91c1c; font-weight:800; font-size:12px;">PAYTM FRAUD DEFENSE WARNING</div>
        <div style="font-size:11px; margin-top:4px; color:#991b1b; line-height:1.45;">
          <strong>Nakli Payment Pakda Gaya:</strong> Grahak ne ₹${amt.toFixed(2)} ka nakli Paytm screen dikhaya (Ref: <code class="tabular-num">${rrn}</code>).<br>
          • <strong>Bank Check:</strong> <span style="font-weight:800; color:#dc2626;">ZERO MONEY DEBITED</span><br>
          • <strong>Account Impact:</strong> ₹0.00 Released (No money given)<br>
          • <strong>Soundbox Alert:</strong> Security Warning Chime Played<br>
          <div style="margin-top:6px; background:#fee2e2; border:1px solid #fca5a5; padding:6px 8px; border-radius:6px; color:#7f1d1d; font-weight:700;">
            Warning: Samaan na dein! This was a fake payment attempt.
          </div>
        </div>
        <div class="wa-ts">${timeStr}</div>
      `;
      playAudio('/static/audio/chirp_security_warning.wav');
    } else if (amt >= 5000) {
      botDiv.innerHTML = `
        <div style="color:#b45309; font-weight:700;">Large Amount Manager Review</div>
        <div style="font-size:11px; margin-top:4px;">Dispute for <strong>₹${amt.toFixed(2)}</strong> (Ref: <span class="tabular-num">${rrn}</span>) is above the ₹5,000 safety limit.</div>
        <div style="font-size:11px; margin-top:4px; color:#4b5563;">An Operations Manager has received this on their desk for 1-click review.</div>
        <div class="wa-ts">${timeStr}</div>
      `;
    } else {
      botDiv.innerHTML = `
        <div><strong>Payment Verified &amp; Added to Balance</strong></div>
        <div style="font-size:11px; margin-top:2px; color:#374151;">Fixed in under 45 seconds automatically.</div>
        <div style="background:#f8fafc; border:1px solid #cbd5e1; border-radius:6px; padding:8px; margin-top:6px; font-size:11px;">
          <div><strong>Amount:</strong> <span class="tabular-num">₹${amt.toFixed(2)}</span></div>
          <div><strong>Reference No:</strong> <span class="tabular-num">${rrn}</span></div>
          <div><strong>Status:</strong> Added to Merchant Settlement Account</div>
          <div><strong>Digital Seal:</strong> <code class="tabular-num">SHA256-SETU-OK</code></div>
        </div>
        <div class="wa-ts">${timeStr}</div>
      `;
      playAudio('/static/audio/chirp_410294820192.wav');
    }
    messagesArea.appendChild(botDiv);
    messagesArea.scrollTop = messagesArea.scrollHeight;
  }
}

function sendWhatsAppQuick(text, amt, rrn) {
  sendWhatsAppMessage(text, amt, rrn);
}

// --------------------------------------------------------------------------
// Initialize on Page Load
// --------------------------------------------------------------------------
window.onload = () => {
  initWS();
  refreshBalances();
  updateBillAmountDisplay(currentBillAmount);
};

