// ======================= 팀 관리 로직 =======================

function setupTeamManagement() {
    const createForm = document.getElementById("team-create-form");
    if (createForm) {
        createForm.addEventListener("submit", createTeam);
    }

    // Collapsible logic
    const header = document.querySelector(".team-mgmt-header");
    const content = document.getElementById("team-mgmt-content");
    const icon = document.getElementById("team-mgmt-toggle-icon");

    if (header && content && icon) {
        // Default Closed
        content.style.display = "none";
        icon.textContent = "▼";

        header.addEventListener("click", () => {
            const isHidden = content.style.display === "none";
            content.style.display = isHidden ? "block" : "none";
            icon.textContent = isHidden ? "▲" : "▼";
        });
    }
}

function getTeamColor(teamName) {
    if (!TEAM_CACHE) return "#cccccc";
    const team = TEAM_CACHE.find(t => t.name === teamName);
    return team ? (team.color || "#cccccc") : "#cccccc";
}

function getTeamColorByPlayer(playerName) {
    if (!TEAM_CACHE) return "#cccccc";
    // Find which team this player belongs to
    const team = TEAM_CACHE.find(t => t.members && t.members.some(m => m.player_name === playerName));
    return team ? (team.color || "#cccccc") : "#cccccc";
}

async function loadTeams() {
    const container = document.getElementById("team-list-container");
    if (!container) return;

    try {
        const teams = await fetchJSON("/api/teams");
        container.innerHTML = "";

        if (!teams || teams.length === 0) {
            container.innerHTML = '<p class="hint-text">등록된 팀이 없습니다.</p>';
            return;
        }

        teams.forEach(t => {
            const card = document.createElement("div");
            card.className = "team-card";

            // Header: Name + Color + Delete Button
            const header = document.createElement("div");
            header.className = "team-header";

            const nameArea = document.createElement("div");
            nameArea.style.display = "flex";
            nameArea.style.alignItems = "center";
            nameArea.style.gap = "8px";

            // Logo Image
            const logoImg = document.createElement("div");
            logoImg.style.width = "40px";
            logoImg.style.height = "40px";
            logoImg.style.overflow = "hidden";
            logoImg.style.display = "flex";
            logoImg.style.alignItems = "center";
            logoImg.style.justifyContent = "center";
            logoImg.style.flexShrink = "0";

            if (t.logo) {
                const img = document.createElement("img");
                img.src = `${t.logo}?t=${new Date().getTime()}`; // Cache busting
                img.style.width = "100%";
                img.style.height = "100%";
                img.style.objectFit = "cover";
                logoImg.appendChild(img);
            } else {
                // Initial if no logo
                logoImg.style.backgroundColor = t.color || "#cccccc";
                logoImg.textContent = t.name.charAt(0);
                logoImg.style.color = "#fff";
                logoImg.style.fontWeight = "bold";
                logoImg.style.fontSize = "1.2em";
            }

            // Logo Change Button / Input
            const uploadWrap = document.createElement("div");
            uploadWrap.style.position = "relative";
            uploadWrap.style.cursor = "pointer";

            const uploadBtnLabel = document.createElement("label");
            uploadBtnLabel.className = "edit-btn"; // using existing styles or just inline
            uploadBtnLabel.style.display = "inline-flex";
            uploadBtnLabel.style.alignItems = "center";
            uploadBtnLabel.style.justifyContent = "center";
            uploadBtnLabel.style.background = "#eeeeee";
            uploadBtnLabel.style.border = "1px solid #ccc";
            uploadBtnLabel.style.borderRadius = "4px";
            uploadBtnLabel.style.padding = "2px 6px";
            uploadBtnLabel.style.fontSize = "0.8em";
            uploadBtnLabel.style.cursor = "pointer";
            uploadBtnLabel.textContent = "로고 변경";

            const fileInput = document.createElement("input");
            fileInput.type = "file";
            fileInput.accept = "image/*";
            fileInput.style.display = "none";
            fileInput.onchange = (e) => {
                if (e.target.files && e.target.files.length > 0) {
                    uploadTeamLogo(t.id, e.target.files[0]);
                }
            };

            uploadBtnLabel.appendChild(fileInput);
            uploadWrap.appendChild(uploadBtnLabel);

            const colorInput = document.createElement("input");
            colorInput.type = "color";
            colorInput.value = t.color || "#cccccc";
            colorInput.style.width = "24px";
            colorInput.style.height = "24px";
            colorInput.style.border = "none";
            colorInput.style.padding = "0";
            colorInput.style.backgroundColor = "transparent";
            colorInput.style.cursor = "pointer";
            colorInput.title = "색상 변경";
            colorInput.onchange = (e) => updateTeamColor(t.id, e.target.value);

            const nameTitle = document.createElement("h3");
            nameTitle.textContent = t.name;
            nameTitle.style.margin = "0";

            nameArea.appendChild(logoImg);
            nameArea.appendChild(uploadWrap);
            nameArea.appendChild(colorInput);
            nameArea.appendChild(nameTitle);

            header.appendChild(nameArea);

            const delBtn = document.createElement("button");
            delBtn.className = "danger-btn";
            delBtn.textContent = "팀 삭제";
            delBtn.style.padding = "2px 6px";
            delBtn.style.fontSize = "0.8em";
            delBtn.onclick = () => deleteTeam(t.id);
            header.appendChild(delBtn);

            card.appendChild(header);

            // Members List
            const membersDiv = document.createElement("div");
            membersDiv.className = "team-members";
            if (t.members && t.members.length > 0) {
                t.members.forEach(m => {
                    const chip = document.createElement("span");
                    chip.className = "team-member-chip";
                    chip.innerHTML = `
            ${m.player_name}
            <span class="del-btn" onclick="deleteTeamMember(${m.id})">×</span>
          `;
                    membersDiv.appendChild(chip);
                });
            } else {
                membersDiv.textContent = "멤버 없음";
            }
            card.appendChild(membersDiv);

            // Add Member Form
            const addDiv = document.createElement("div");
            addDiv.className = "team-add-member";
            addDiv.innerHTML = `
        <input type="text" placeholder="멤버 추가" id="team-add-input-${t.id}">
        <button onclick="addTeamMember(${t.id})">추가</button>
      `;
            card.appendChild(addDiv);

            container.appendChild(card);
        });

    } catch (e) {
        console.error(e);
        container.innerHTML = '<p class="hint-text">로드 실패</p>';
    }
}

async function createTeam(e) {
    e.preventDefault();
    const form = e.target;
    const nameInput = form.querySelector("input[name='name']");
    const colorInput = form.querySelector("input[name='color']"); // 색상 입력지
    const name = nameInput.value.trim();
    const color = colorInput ? colorInput.value : "#000000";

    if (!name) return alert("팀 이름을 입력하세요.");

    try {
        await fetchJSON("/api/teams", {
            method: "POST",
            body: JSON.stringify({ name, color })
        });
        nameInput.value = "";
        loadTeams();
    } catch (err) {
        alert("팀 생성 실패: " + err.message);
    }
}

async function deleteTeam(teamId) {
    if (!confirm("정말 이 팀을 삭제하시겠습니까? (멤버 정보도 함께 삭제됩니다)")) return;
    try {
        await fetchJSON(`/api/teams/${teamId}`, { method: "DELETE" });
        loadTeams();
    } catch (err) {
        alert("팀 삭제 실패: " + err.message);
    }
}

async function updateTeamColor(teamId, newColor) {
    try {
        await fetchJSON(`/api/teams/${teamId}`, {
            method: "PUT",
            body: JSON.stringify({ color: newColor })
        });
        // UI is already updated by input change, so no need to reload
    } catch (err) {
        alert("색상 변경 실패: " + err.message);
        loadTeams(); // Revert to previous state
    }
}

async function uploadTeamLogo(teamId, file) {
    const formData = new FormData();
    formData.append("logo", file);

    try {
        const res = await fetch(`/api/teams/${teamId}/logo`, {
            method: "POST",
            body: formData
        });
        if (!res.ok) {
            const data = await res.json();
            throw new Error(data.error || "Upload failed");
        }
        loadTeams(); // Reload to show new logo
    } catch (err) {
        alert("로고 업로드 실패: " + err.message);
    }
}

async function addTeamMember(teamId) {
    const input = document.getElementById(`team-add-input-${teamId}`);
    if (!input) return;
    const name = input.value.trim();
    if (!name) return alert("멤버 이름을 입력하세요.");

    try {
        await fetchJSON(`/api/teams/${teamId}/members`, {
            method: "POST",
            body: JSON.stringify({ player_name: name })
        });
        loadTeams();
    } catch (err) {
        alert("멤버 추가 실패: " + err.message);
    }
}

async function deleteTeamMember(memberId) {
    if (!confirm("이 멤버를 팀에서 제외하시겠습니까?")) return;
    try {
        await fetchJSON(`/api/team_members/${memberId}`, { method: "DELETE" });
        loadTeams();
    } catch (err) {
        alert("멤버 삭제 실패: " + err.message);
    }
}

// ======================= 팀 대국 기록 입력 로직 =======================

let TEAM_CACHE = []; // Teams with members

async function setupTeamGameForm() {
    const form = document.getElementById("team-game-form");
    const inputsDiv = document.getElementById("team-game-inputs");
    if (!form || !inputsDiv) return;

    // Render 4 rows
    inputsDiv.innerHTML = "";
    const positions = ["P1(동)", "P2(남)", "P3(서)", "P4(북)"];

    for (let i = 1; i <= 4; i++) {
        const row = document.createElement("div");
        row.className = "team-game-row";
        row.innerHTML = `
      <label>${positions[i - 1]}</label>
      <select name="player${i}_team" id="team-select-${i}" required>
        <option value="">팀 선택</option>
      </select>
      <select name="player${i}_player" id="player-select-${i}" required>
        <option value="">멤버 선택</option>
      </select>
      <input type="number" name="player${i}_score" placeholder="점수" required>
    `;
        inputsDiv.appendChild(row);
    }

    // Bind change events for team selects
    for (let i = 1; i <= 4; i++) {
        const ts = document.getElementById(`team-select-${i}`);
        ts.addEventListener("change", (e) => updateMemberSelect(i, e.target.value));
    }

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const fd = new FormData(form);
        const payload = {};

        let total = 0;
        for (let i = 1; i <= 4; i++) {
            const tid = fd.get(`player${i}_team`);
            const pid = fd.get(`player${i}_player`); // This is player name
            const score = parseInt(fd.get(`player${i}_score`));

            if (!tid || !pid || isNaN(score)) return alert("모든 항목을 입력하세요.");

            const team = TEAM_CACHE.find(t => t.id == tid);
            const teamName = team ? team.name : "";

            payload[`player${i}`] = {
                team_id: tid,
                name: pid,
                score: score
            };
            total += score;
        }

        if (total !== 100000) return alert(`점수 합이 100000이 되어야 합니다. (현재: ${total})`);

        try {
            await fetchJSON("/api/team_games", {
                method: "POST",
                body: JSON.stringify(payload)
            });
            form.reset();
            form.reset();
            loadTeamGames();
        } catch (err) {
            alert("기록 저장 실패: " + err.message);
        }
    });

    // Load teams and populate selects
    await refreshTeamCache();
}

async function refreshTeamCache() {
    try {
        TEAM_CACHE = await fetchJSON("/api/teams");
        for (let i = 1; i <= 4; i++) {
            const el = document.getElementById(`team-select-${i}`);
            if (el) {
                const current = el.value;
                el.innerHTML = '<option value="">팀 선택</option>';
                TEAM_CACHE.forEach(t => {
                    const opt = document.createElement("option");
                    opt.value = t.id;
                    opt.textContent = t.name;
                    el.appendChild(opt);
                });
                el.value = current;
            }
        }
    } catch (e) { console.error(e); }
}

function updateMemberSelect(index, teamId) {
    const ps = document.getElementById(`player-select-${index}`);
    if (!ps) return;

    ps.innerHTML = '<option value="">멤버 선택</option>';
    if (!teamId) return;

    const team = TEAM_CACHE.find(t => t.id == teamId);
    if (team && team.members) {
        team.members.forEach(m => {
            const opt = document.createElement("option");
            opt.value = m.player_name;
            opt.textContent = m.player_name;
            ps.appendChild(opt);
        });
    }
}




async function loadTeamGames() {
    await refreshTeamCache();

    try {
        const tbody = document.getElementById("team-games-tbody");
        if (!tbody) return;

        const games = await fetchJSON("/api/team_games");
        tbody.innerHTML = "";

        if (!games || games.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="ranking-placeholder">기록이 없습니다.</td></tr>';
            return;
        }

        games.forEach(g => {
            const tr = document.createElement("tr");

            const sData = [
                Number(g.player1_score),
                Number(g.player2_score),
                Number(g.player3_score),
                Number(g.player4_score)
            ];
            const pts = calcPts(sData);

            const pData = [
                { t: g.player1_team_name, n: g.player1_name, s: sData[0], p: pts[0] },
                { t: g.player2_team_name, n: g.player2_name, s: sData[1], p: pts[1] },
                { t: g.player3_team_name, n: g.player3_name, s: sData[2], p: pts[2] },
                { t: g.player4_team_name, n: g.player4_name, s: sData[3], p: pts[3] },
            ];

            const maxScore = Math.max(...sData);

            let playerCells = "";
            for (let i = 0; i < 4; i++) {
                const p = pData[i];
                // Remove + for positive, keep - for negative
                const ptStr = `${p.p}`;

                const isWinner = (p.s === maxScore);
                const cellClass = isWinner ? 'class="winner-cell"' : '';

                const color = getTeamColor(p.t);

                playerCells += `
          <td ${cellClass}>
            <div style="display:flex; align-items:center; justify-content:center; gap:6px; font-size:0.9em; color:#555; margin-bottom:2px;">
              <div style="width:10px; height:10px; border-radius:20%; background-color:${color};"></div>
              ${p.t}
            </div>
            <div style="font-weight:bold;">${p.n}</div>
            <span style="font-weight:normal; font-size:0.9em;">${p.s}</span> <span style="font-weight:normal; font-size:0.9em;">(${ptStr})</span>
          </td>
        `;
            }

            tr.innerHTML = `
        <td>${g.id}</td>
        <td>${formatKoreanTime(g.created_at)}</td>
        ${playerCells}
        <td><button class="danger-btn" onclick="deleteTeamGame(${g.id})">삭제</button></td>
      `;
            tbody.appendChild(tr);
        });

    } catch (e) {
        console.error(e);
        const tbody = document.getElementById("team-games-tbody");
        if (tbody) tbody.innerHTML = '<tr><td colspan="6" class="ranking-placeholder">로드 실패</td></tr>';
    }
}

async function deleteTeamGame(id) {
    if (!confirm("이 대국 기록을 삭제하시겠습니까?")) return;
    try {
        await fetchJSON(`/api/team_games/${id}`, { method: "DELETE" });
        loadTeamGames();
    } catch (e) {
        alert("삭제 실패: " + e.message);
    }
}


async function loadTeamRanking() {
    const container = document.getElementById("team-ranking-container");
    if (!container) return;

    container.innerHTML = '<p class="loading-text">로딩 중...</p>';

    try {
        const [data, games] = await Promise.all([
            fetchJSON("/api/team_ranking"),
            fetchJSON("/api/team_games")
        ]);

        container.innerHTML = "";

        // --- Build cumulative PT chart data ---
        const sortedGames = (games || []).slice().sort((a, b) => a.id - b.id);
        const teamNames = (data || []).map(t => t.name);
        const ptRunning = {};
        const cumulPt = {};
        teamNames.forEach(n => { ptRunning[n] = 0; cumulPt[n] = [0]; }); // Start at 0
        const gameLabels = [0]; // Game 0 = starting point

        sortedGames.forEach(g => {
            const players = [
                { team: g.player1_team_name, score: Number(g.player1_score) },
                { team: g.player2_team_name, score: Number(g.player2_score) },
                { team: g.player3_team_name, score: Number(g.player3_score) },
                { team: g.player4_team_name, score: Number(g.player4_score) },
            ];
            const pts = calcPts(players.map(p => p.score));

            const gamePtByTeam = {};
            players.forEach((p, i) => {
                if (!p.team) return;
                gamePtByTeam[p.team] = (gamePtByTeam[p.team] || 0) + pts[i];
            });

            const participates = teamNames.some(n => gamePtByTeam[n] !== undefined);
            if (!participates) return;

            gameLabels.push(g.id);
            teamNames.forEach(n => {
                if (gamePtByTeam[n] !== undefined) ptRunning[n] += gamePtByTeam[n];
                cumulPt[n].push(+ptRunning[n].toFixed(1));
            });
        });

        // --- Render chart ---
        if (gameLabels.length > 0) {
            const chartArea = document.getElementById("team-ranking-chart-area");
            if (chartArea) {
                chartArea.innerHTML = "";
                const canvas = document.createElement("canvas");
                canvas.id = "team-ranking-chart";
                canvas.height = 180;
                chartArea.appendChild(canvas);

                if (window._teamRankingChart) window._teamRankingChart.destroy();

                window._teamRankingChart = new Chart(canvas, {
                    type: "line",
                    data: {
                        labels: gameLabels,
                        datasets: teamNames.map(name => ({
                            label: name,
                            data: cumulPt[name] || [],
                            borderColor: getTeamColor(name),
                            backgroundColor: getTeamColor(name) + "22",
                            pointBackgroundColor: getTeamColor(name),
                            borderWidth: 2,
                            pointRadius: 3,
                            tension: 0,
                            fill: false,
                        }))
                    },
                    options: {
                        responsive: true,
                        animation: false,
                        plugins: {
                            legend: { position: "top", labels: { boxWidth: 12, font: { size: 11 } } },
                            tooltip: { mode: "index", intersect: false }
                        },
                        scales: {
                            x: { title: { display: true, text: "게임 ID", font: { size: 11 } }, ticks: { font: { size: 10 } } },
                            y: { title: { display: true, text: "누적 pt", font: { size: 11 } }, ticks: { font: { size: 10 } } }
                        }
                    }
                });
            }

            // --- Render ranking table ---
            const table = document.createElement("table");
            table.className = "ranking-table";
            table.innerHTML = `
      <thead>
        <tr>
          <th style="width: 30px;">순위</th>
          <th style="width: 130px;">팀</th>
          <th style="width: 50px;">게임 수</th>
          <th style="width: 50px;">총 pt</th>
          <th style="width: 50px;">평균 pt</th>
          <th style="width: 50px;">연대율</th>
          <th style="width: 200px;">등수 분포</th>
        </tr>
      </thead>
      <tbody id="team-ranking-tbody">
      </tbody>
    `;

            const tbody = table.querySelector("tbody");

            if (!data || data.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" class="ranking-placeholder">기록이 없습니다</td></tr>';
            } else {
                data.forEach((t, index) => {
                    const rankCounts = t.rank_counts || [0, 0, 0, 0];
                    const rendaCount = rankCounts[0] + rankCounts[1];
                    const rendaRate = t.games > 0 ? (rendaCount / t.games) * 100 : 0.0;

                    const team = TEAM_CACHE.find(tc => tc.name === t.name);
                    let logoHtml = "";
                    if (team && team.logo) {
                        logoHtml = `<img src="${team.logo}?t=${new Date().getTime()}" style="height:100%; width:auto; aspect-ratio:1/1; object-fit:cover; display:block; flex-shrink:0;" />`;
                    } else if (team) {
                        logoHtml = `<div style="height:100%; aspect-ratio:1/1; background-color:${team.color || '#cccccc'}; display:flex; align-items:center; justify-content:center; color:#fff; font-weight:bold; font-size:14px; flex-shrink:0;">${t.name.charAt(0)}</div>`;
                    } else {
                        logoHtml = `<div style="height:100%; aspect-ratio:1/1; background-color:#cccccc; display:flex; align-items:center; justify-content:center; color:#fff; font-weight:bold; font-size:14px; flex-shrink:0;">?</div>`;
                    }

                    const teamColor = team ? (team.color || '#cccccc') : '#cccccc';
                    const tr = document.createElement("tr");
                    tr.innerHTML = `
          <td>${index + 1}</td>
          <td style="padding:0px; padding-right:0px; text-align:left; position:relative;">
            <div style="position:absolute; top:0; left:0; width:100%; height:100%; pointer-events:none; background: linear-gradient(90deg, ${teamColor}FF 40%, transparent 90%); z-index:0;"></div>
            <div style="display:flex; align-items:center; height:20px; gap:4px; position:relative; z-index:1;">
              <div style="display:flex; height:100%;">${logoHtml}</div>
              <span style="font-weight:600; text-shadow:0 0 2px rgba(255,255,255,0.8);">${t.name}</span>
            </div>
          </td>
          <td>${t.games}</td>
          <td>${t.total_pt}</td>
          <td>${t.avg_pt}</td>
          <td>${rendaRate.toFixed(1)}%</td>
          <td style="text-align: left; padding: 4px 8px;"></td>
        `;
                    tr.children[6].appendChild(createRankDistBar(rankCounts, t.games));
                    tbody.appendChild(tr);
                });
            }

            container.appendChild(table);

        } // end if gameLabels.length > 0

    } catch (err) {
        console.error(err);
        container.innerHTML = '<p class="error-text">랭킹 로드 실패</p>';
    }
}



async function loadTeamPersonalRanking() {
    const container = document.getElementById("team-personal-ranking-container");
    if (!container) return;

    container.innerHTML = '<p class="loading-text">로딩 중...</p>';

    try {
        // 1. Fetch Team Games
        const games = await fetchJSON("/api/team_games");

        // 2. Calculate Stats
        // Reusing calculateStatsFromGames which works for general game objects
        const stats = calculateStatsFromGames(games || []);

        // 3. Sort by Total Pt (desc)
        stats.sort((a, b) => b.total_pt - a.total_pt);

        // 4. Render Table
        const table = document.createElement("table");
        table.className = "ranking-table";
        table.innerHTML = `
      <thead>
        <tr>
          <th style="width: 30px;">순위</th>
          <th style="width: 130px;">이름</th>
          <th style="width: 50px;">게임 수</th>
          <th style="width: 50px;">총 pt</th>
          <th style="width: 50px;">평균 pt</th>
          <th style="width: 50px;">연대율</th>
          <th style="width: 200px;">등수 분포</th>
        </tr>
      </thead>
      <tbody id="team-personal-ranking-tbody">
      </tbody>
    `;

        const tbody = table.querySelector("tbody");

        if (stats.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="ranking-placeholder">기록이 없습니다</td></tr>';
        } else {
            stats.forEach((p, index) => {
                const rankCounts = p.rankCounts || [0, 0, 0, 0];
                const rendaRate = p.yonde_rate || 0.0;

                const team = TEAM_CACHE.find(tc => tc.members && tc.members.some(m => m.player_name === p.name));
                let logoHtml = "";
                if (team && team.logo) {
                    logoHtml = `<img src="${team.logo}?t=${new Date().getTime()}" style="height:100%; width:auto; aspect-ratio:1/1; object-fit:cover; display:block; flex-shrink:0;" />`;
                } else if (team) {
                    logoHtml = `<div style="height:100%; aspect-ratio:1/1; background-color:${team.color || '#cccccc'}; display:flex; align-items:center; justify-content:center; color:#fff; font-weight:bold; font-size:14px; flex-shrink:0;">${team.name.charAt(0)}</div>`;
                } else {
                    logoHtml = `<div style="height:100%; aspect-ratio:1/1; background-color:#cccccc; display:flex; align-items:center; justify-content:center; color:#fff; font-weight:bold; font-size:14px; flex-shrink:0;">?</div>`;
                }

                const teamColor = team ? (team.color || '#cccccc') : '#cccccc';
                const tr = document.createElement("tr");
                tr.innerHTML = `
          <td>${index + 1}</td>
          <td style="padding:0px; padding-right:0px; text-align:left; position:relative;">
            <div style="position:absolute; top:0; left:0; width:100%; height:100%; pointer-events:none; background: linear-gradient(90deg, ${teamColor}FF 40%, transparent 90%); z-index:0;"></div>
            <div style="display:flex; align-items:center; height:20px; gap:4px; position:relative; z-index:1;">
              <div style="display:flex; height:100%;">${logoHtml}</div>
              <span style="font-weight:600; text-shadow:0 0 2px rgba(255,255,255,0.8);">${p.name}</span>
            </div>
          </td>
          <td>${p.games}</td>
          <td>${p.total_pt.toFixed(1)}</td>
          <td>${(p.total_pt / p.games).toFixed(1)}</td>
          <td>${rendaRate.toFixed(1)}%</td>
          <td style="text-align: left; padding: 4px 8px;"></td>
        `;

                // Append the graph to the last cell
                tr.children[6].appendChild(createRankDistBar(p.rankCounts, p.games));
                tbody.appendChild(tr);
            });
        }

        container.innerHTML = "";
        container.appendChild(table);

    } catch (err) {
        console.error(err);
        container.innerHTML = '<p class="error-text">개인 랭킹 로드 실패</p>';
    }
}

function renderTeamView() {
    refreshTeamCache();
    loadTeams();
    loadTeamGames();
    loadTeamRanking();
    loadTeamPersonalRanking();
}
