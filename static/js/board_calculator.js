(function () {
    const panels = Array.from(document.querySelectorAll("[data-board-calculator]"));
    if (!panels.length) return;

    function number(value, fallback = 0) {
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed : fallback;
    }

    function calculate(values) {
        const boardWidth = number(values.board_width);
        const boardHeight = number(values.board_height);
        const partWidth = number(values.part_width);
        const partHeight = number(values.part_height);
        const quantity = Math.floor(number(values.quantity));
        const margin = number(values.margin);
        const spacing = Math.max(0, number(values.spacing));
        if (Math.min(boardWidth, boardHeight, partWidth, partHeight, quantity) <= 0) {
            return { error: "请输入大于 0 的板材尺寸、零件尺寸和数量。" };
        }
        if (margin < 0) return { error: "边距不能小于 0。" };
        const usableWidth = boardWidth - margin * 2;
        const usableHeight = boardHeight - margin * 2;
        if (usableWidth <= 0 || usableHeight <= 0) return { error: "边距过大，板材可用尺寸不足。" };
        const piecesPerRow = Math.floor((usableWidth + spacing) / (partWidth + spacing));
        const rowsPerBoard = Math.floor((usableHeight + spacing) / (partHeight + spacing));
        const piecesPerBoard = Math.max(0, piecesPerRow) * Math.max(0, rowsPerBoard);
        if (piecesPerBoard <= 0) return { error: "当前零件尺寸无法排入板材，请检查尺寸、边距和间距。" };
        const neededBoards = Math.ceil(quantity / piecesPerBoard);
        const utilizationRate = ((quantity * partWidth * partHeight) / (neededBoards * boardWidth * boardHeight)) * 100;
        return {
            pieces_per_row: piecesPerRow,
            rows_per_board: rowsPerBoard,
            pieces_per_board: piecesPerBoard,
            needed_boards: neededBoards,
            utilization_rate: utilizationRate.toFixed(2),
        };
    }

    function collect(panel) {
        const values = {};
        panel.querySelectorAll("[data-board-input]").forEach((input) => {
            values[input.dataset.boardInput] = input.value;
        });
        return values;
    }

    function render(panel, result) {
        const node = panel.querySelector("[data-board-result]");
        if (!node) return;
        if (result.error) {
            node.innerHTML = `<p class="message error">${result.error}</p>`;
            panel.dataset.neededBoards = "";
            return;
        }
        panel.dataset.neededBoards = result.needed_boards;
        node.innerHTML = `
            <div class="board-result-grid">
                <div class="mini-card"><span>每行件数</span><strong>${result.pieces_per_row}</strong></div>
                <div class="mini-card"><span>每列件数</span><strong>${result.rows_per_board}</strong></div>
                <div class="mini-card"><span>每张板排多少件</span><strong>${result.pieces_per_board}</strong></div>
                <div class="mini-card"><span>需要板数</span><strong>${result.needed_boards}</strong></div>
                <div class="mini-card"><span>材料利用率</span><strong>${result.utilization_rate}%</strong></div>
            </div>
        `;
    }

    panels.forEach((panel) => {
        const recalc = () => render(panel, calculate(collect(panel)));
        panel.addEventListener("input", recalc);
        panel.addEventListener("change", recalc);
        panel.querySelector("[data-write-board-count]")?.addEventListener("click", () => {
            recalc();
            const boardCount = panel.dataset.neededBoards;
            const target = document.querySelector('[data-field="board_count"]');
            if (!boardCount || !target) return;
            target.value = boardCount;
            target.dispatchEvent(new Event("input", { bubbles: true }));
        });
        recalc();
    });
})();
