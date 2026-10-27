// Atualiza a pagina de monitoramento por polling (a cada 3 s) em /api/status
const INTERVALO_MS = 3000;

const ROTULOS = {
  entrada: "Entrada", saida: "Saída", acesso_negado: "Acesso negado",
  invasao: "Invasão", movimento_sem_cracha: "Movimento sem crachá", campainha: "Campainha",
};

function hora(iso) {
  return iso ? iso.replace("T", " ").slice(0, 19) : "";
}

function duracao(seg) {
  if (seg == null) return "";
  const m = Math.floor(seg / 60), s = seg % 60;
  return ` (${m} min ${s} s)`;
}

function preencher(id, itens, formatar, vazio) {
  const ul = document.getElementById(id);
  ul.innerHTML = "";
  if (!itens.length) {
    ul.innerHTML = `<li class="vazio">${vazio}</li>`;
    return;
  }
  for (const it of itens) {
    const li = document.createElement("li");
    li.innerHTML = formatar(it);
    ul.appendChild(li);
  }
}

async function atualizar() {
  let d;
  try {
    const r = await fetch("/api/status", { cache: "no-store" });
    d = await r.json();
  } catch (e) {
    document.getElementById("disp-texto").textContent = "servidor sem resposta";
    return;
  }

  // Estado da Raspberry
  const disp = d.dispositivo;
  const ponto = document.getElementById("disp-online");
  ponto.className = "ponto " + (disp.online ? "on" : "off");
  document.getElementById("disp-texto").textContent = disp.online
    ? `Raspberry online (${disp.ip || "?"})`
    : (disp.ultimo_contato ? `Raspberry offline desde ${hora(disp.ultimo_contato)}` : "Raspberry nunca conectou");
  const luz = document.getElementById("disp-luz");
  if (disp.luz) {
    luz.hidden = false;
    luz.textContent = disp.luz === "clara" ? "sala iluminada" : "sala escura";
    luz.className = "tag " + (disp.luz === "clara" ? "amarelo" : "cinza");
  } else {
    luz.hidden = true;
  }
  if (disp.eventos_pendentes > 0) {
    document.getElementById("disp-texto").textContent += ` · ${disp.eventos_pendentes} evento(s) na fila offline`;
  }
  document.getElementById("relogio").textContent = hora(d.agora).slice(11);

  // Numeros do topo
  const t = d.totais_hoje || {};
  document.getElementById("n-dentro").textContent = d.dentro_da_sala.length;
  document.getElementById("n-entradas").textContent = t.entrada || 0;
  document.getElementById("n-saidas").textContent = t.saida || 0;
  document.getElementById("n-negados").textContent = t.acesso_negado || 0;
  document.getElementById("n-invasoes").textContent = t.invasao || 0;

  // Listas
  preencher("lista-dentro", d.dentro_da_sala,
    e => `<strong>${e.nome}</strong> <small>desde ${hora(e.data_hora).slice(11)}</small>`,
    "Sala vazia");
  preencher("lista-alertas", d.alertas,
    e => `<span class="tag ${e.tipo}">${ROTULOS[e.tipo] || e.tipo}</span> ${e.nome || (e.tag_rfid ? "tag " + e.tag_rfid : "")} <small>${hora(e.data_hora)}</small>`,
    "Nenhum alerta");
  preencher("lista-entradas", d.ultimas_entradas,
    e => `<strong>${e.nome}</strong> <small>${hora(e.data_hora)}</small>`,
    "Nenhuma entrada registrada");
  preencher("lista-saidas", d.ultimas_saidas,
    e => `<strong>${e.nome}</strong> <small>${hora(e.data_hora)}${duracao(e.duracao_segundos)}</small>`,
    "Nenhuma saída registrada");
  preencher("lista-negados", d.acessos_negados,
    e => `<strong>${e.nome || "?"}</strong> <small>${hora(e.data_hora)}</small>`,
    "Nenhuma tentativa");
  preencher("lista-invasoes", d.invasoes,
    e => `tag <code>${e.tag_rfid}</code> <small>${hora(e.data_hora)}</small>`,
    "Nenhuma tentativa");
}

atualizar();
setInterval(atualizar, INTERVALO_MS);
