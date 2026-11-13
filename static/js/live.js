// live.js
// Keeps the leaderboard up to date without reloading the page.
// Every 5 seconds it asks the server for /api/live (JSON) and rebuilds the
// podium, the standings table and the latest results.
// Used by the home page and the big screen page.

const UPDATE_SECONDS = 5;
const ARROW_UPDATES = 6; // an arrow stays up for 6 updates (30 seconds)

let lastTeams = {};  // "nova squad" -> { rank: 2, matches: 4 } from the last update
let arrows = {};     // "nova squad" -> { text: "▲ 2", type: "up", updatesLeft: 6 }
let lastMode = null;

// ---------- Small helpers ----------

function setText(id, text) {
  const element = document.getElementById(id);
  if (element) {
    element.textContent = text;
  }
}

// Makes an element with text in it. textContent (not innerHTML) means a team
// called "<script>" shows up as plain text and can't run code.
function makeElement(tag, text) {
  const element = document.createElement(tag);
  element.textContent = text;
  return element;
}

function placeText(rank) {
  if (rank == 1) return "1ST";
  if (rank == 2) return "2ND";
  return "3RD";
}

function medal(rank) {
  if (rank == 1) return "gold";
  if (rank == 2) return "silver";
  return "bronze";
}

// ---------- Rank arrows ----------

// Compares the new ranks to the last ranks and decides which arrows to show.
// Returns a list of the teams that just played a match, so their rows can flash.
function updateArrows(teams, mode) {
  // Count down the arrows that are already showing.
  for (const key in arrows) {
    arrows[key].updatesLeft = arrows[key].updatesLeft - 1;
    if (arrows[key].updatesLeft <= 0) {
      delete arrows[key];
    }
  }

  // The first time, or if the admin changed how teams are ranked,
  // just remember the ranks without showing arrows.
  const firstTime = lastMode === null || lastMode != mode;
  const justPlayed = [];

  for (const team of teams) {
    const key = team.name.toLowerCase();
    const old = lastTeams[key];

    if (!firstTime) {
      if (old === undefined) {
        arrows[key] = { text: "NEW", type: "new", updatesLeft: ARROW_UPDATES };
      } else if (team.rank < old.rank) {
        arrows[key] = { text: "▲ " + (old.rank - team.rank), type: "up", updatesLeft: ARROW_UPDATES };
      } else if (team.rank > old.rank) {
        arrows[key] = { text: "▼ " + (team.rank - old.rank), type: "down", updatesLeft: ARROW_UPDATES };
      }

      if (old === undefined || team.matches > old.matches) {
        justPlayed.push(key);
      }
    }
  }

  // Remember this update for next time.
  lastTeams = {};
  for (const team of teams) {
    lastTeams[team.name.toLowerCase()] = { rank: team.rank, matches: team.matches };
  }
  lastMode = mode;

  return justPlayed;
}

// ---------- Building the page ----------

function showPodium(data) {
  const podium = document.getElementById("podium");
  podium.textContent = ""; // remove the old cards

  if (data.teams.length == 0) {
    const card = document.createElement("article");
    card.appendChild(makeElement("h3", "Waiting for the first match…"));
    card.appendChild(makeElement("p", "Scores show up here the second they come in."));
    podium.appendChild(card);
    return;
  }

  for (let i = 0; i < 3 && i < data.teams.length; i++) {
    const team = data.teams[i];
    const card = document.createElement("article");
    card.className = "place-" + medal(team.rank);

    const place = makeElement("span", placeText(team.rank));
    place.className = "place";
    card.appendChild(place);

    card.appendChild(makeElement("h3", team.name));

    const score = makeElement("p", team[data.mode]);
    score.className = "podium-score";
    card.appendChild(score);

    card.appendChild(makeElement("small", team.matches + " matches • best " + team.best));
    podium.appendChild(card);
  }
}

function showStandings(data, justPlayed) {
  const table = document.getElementById("standings");
  const limit = Number(table.dataset.limit); // 0 means show every team
  table.textContent = "";

  if (data.teams.length == 0) {
    const row = document.createElement("tr");
    const cell = makeElement("td", "No matches yet.");
    cell.colSpan = 7;
    row.appendChild(cell);
    table.appendChild(row);
    return;
  }

  for (let i = 0; i < data.teams.length; i++) {
    if (limit > 0 && i >= limit) {
      break;
    }
    const team = data.teams[i];
    const key = team.name.toLowerCase();
    const row = document.createElement("tr");

    const rank = makeElement("th", team.rank);
    rank.scope = "row";
    row.appendChild(rank);
    row.appendChild(makeElement("td", team.name));
    row.appendChild(makeElement("td", team.best));
    row.appendChild(makeElement("td", team.total));
    row.appendChild(makeElement("td", team.average));
    row.appendChild(makeElement("td", team.matches));

    const move = makeElement("td", "");
    if (arrows[key]) {
      move.textContent = arrows[key].text;
      move.className = "move-" + arrows[key].type;
    }
    row.appendChild(move);

    if (justPlayed.includes(key)) {
      row.className = "changed";
    }
    table.appendChild(row);
  }

  // Highlight the column the teams are ranked by.
  const headers = document.querySelectorAll("th[data-mode]");
  for (const header of headers) {
    if (header.dataset.mode == data.mode) {
      header.className = "active";
    } else {
      header.className = "";
    }
  }
}

function showRecent(data) {
  const list = document.getElementById("recent");
  list.textContent = "";

  if (data.recent.length == 0) {
    list.appendChild(makeElement("li", "No results yet."));
    return;
  }

  for (const result of data.recent) {
    const item = document.createElement("li");
    item.appendChild(makeElement("strong", result.name));

    const score = makeElement("span", result.score);
    score.className = "score";
    item.appendChild(score);

    item.appendChild(document.createElement("br"));
    const when = makeElement("small", "");
    if (result.new) {
      const tag = makeElement("span", "NEW ");
      tag.className = "new-tag";
      when.appendChild(tag);
    }
    when.appendChild(document.createTextNode(result.ago));
    item.appendChild(when);

    list.appendChild(item);
  }
}

function showBanners(data) {
  document.getElementById("locked-banner").hidden = !data.locked;
  document.getElementById("announcement").hidden = data.announcement == "";
  setText("announcement-text", data.announcement);
}

// ---------- The update loop ----------

async function update() {
  // Don't ask the server for updates if nobody is looking at this tab.
  if (document.hidden) {
    return;
  }

  try {
    const response = await fetch("/api/live");
    if (!response.ok) {
      throw new Error("The server answered " + response.status);
    }
    const data = await response.json();

    const justPlayed = updateArrows(data.teams, data.mode);
    showBanners(data);
    showPodium(data);
    showStandings(data, justPlayed);
    showRecent(data);

    setText("team-count", data.teams.length);
    setText("match-count", data.match_count);
    setText("mode-label", data.mode_label);
    setText("live-status", "Live • updated " + new Date().toLocaleTimeString());
    document.getElementById("live-dot").className = "live-dot";
  } catch (error) {
    // Keep showing the last scores and try again next time.
    setText("live-status", "Connection lost, retrying…");
    document.getElementById("live-dot").className = "live-dot offline";
  }
}

update();
setInterval(update, UPDATE_SECONDS * 1000);
