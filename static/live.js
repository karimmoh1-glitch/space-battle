// live.js
// Python builds the leaderboard. This script just asks for the newest copy
// every 3 seconds and puts it on the page, so nobody has to press refresh.

const board = document.getElementById("live-board");
const statusLabel = document.getElementById("live-status");
const updatedLabel = document.getElementById("last-updated");
const warning = document.getElementById("connection-warning");
const announcer = document.getElementById("announcer");

let hasLoaded = false;
let lastLeader = "";

function showConnected() {
    hasLoaded = true;
    warning.hidden = true;

    const isEmpty = board.querySelector("[data-empty]") !== null;
    statusLabel.textContent = isEmpty ? "Awaiting first match" : "Live";
    statusLabel.className = isEmpty ? "status" : "status status-live";
    updatedLabel.textContent = "Updated " + new Date().toLocaleTimeString();

    // Tell screen readers only when first place changes, not every 3 seconds.
    const leader = board.querySelector("[data-leader]");
    if (leader && leader.dataset.leader !== lastLeader) {
        lastLeader = leader.dataset.leader;
        announcer.textContent = lastLeader;
    }
}

function showProblem() {
    if (hasLoaded) {
        statusLabel.textContent = "Reconnecting";
        warning.hidden = false;
    } else {
        statusLabel.textContent = "Signal lost";
        board.innerHTML = '<div class="panel message"><h2>Signal lost</h2>' +
            "<p>The scoreboard cannot reach the server. It will keep trying by itself.</p></div>";
    }
    statusLabel.className = "status status-warning";
}

async function refreshBoard() {
    // Do not use the network while nobody is looking at this tab.
    if (!document.hidden) {
        try {
            const response = await fetch(board.dataset.url, { signal: AbortSignal.timeout(8000) });
            if (!response.ok) {
                throw new Error("Server said " + response.status);
            }
            board.innerHTML = await response.text();
            showConnected();
        } catch (error) {
            showProblem();
        }
    }
    // Waiting until now means a slow answer can never cause requests to pile up.
    setTimeout(refreshBoard, 3000);
}

refreshBoard();
