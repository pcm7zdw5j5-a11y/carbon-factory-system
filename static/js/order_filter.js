(function () {
    const form = document.querySelector("[data-order-filter-form]");
    if (!form) return;

    const keywordInput = form.querySelector("[data-filter-keyword]");
    const statusSelect = form.querySelector("[data-filter-status]");
    const sourceSelect = form.querySelector("[data-filter-source]");
    const profitSelect = form.querySelector("[data-filter-profit]");
    const clearButton = form.querySelector("[data-filter-clear]");
    const items = Array.from(document.querySelectorAll("[data-order-item]"));
    const summary = document.querySelector("[data-filter-summary]");
    const emptyMessage = document.querySelector("[data-filter-empty]");
    const total = new Set(items.map((item) => item.dataset.orderNo)).size || items.length;

    function normalize(value) {
        return String(value || "").trim().toLowerCase();
    }

    function orderKey(item) {
        return item.dataset.orderNo || "";
    }

    function matchesKeyword(item, keyword) {
        if (!keyword) return true;
        const searchable = [
            item.dataset.orderNo,
            item.dataset.customer,
            item.dataset.phone,
            item.dataset.product,
            item.dataset.remark,
        ].map(normalize).join(" ");
        return searchable.includes(keyword);
    }

    function applyFilters() {
        const keyword = normalize(keywordInput?.value);
        const status = statusSelect?.value || "";
        const source = sourceSelect?.value || "";
        const profitAlert = profitSelect?.value || "";
        const visibleKeys = new Set();

        items.forEach((item) => {
            const statusOk = !status || item.dataset.status === status;
            const sourceOk = !source || item.dataset.source === source;
            const keywordOk = matchesKeyword(item, keyword);
            const itemProfitAlert = item.dataset.profitAlert || "normal";
            const profitOk =
                !profitAlert ||
                (profitAlert === "alert" && ["low", "danger", "loss"].includes(itemProfitAlert)) ||
                itemProfitAlert === profitAlert;
            const visible = statusOk && sourceOk && keywordOk && profitOk;
            item.hidden = !visible;
            if (visible) visibleKeys.add(orderKey(item));
        });

        const visibleCount = visibleKeys.size;
        if (summary) {
            summary.textContent = `共 ${total} 条，当前显示 ${visibleCount} 条`;
        }
        if (emptyMessage) {
            emptyMessage.hidden = visibleCount !== 0;
        }
    }

    function clearFilters() {
        if (keywordInput) keywordInput.value = "";
        if (statusSelect) statusSelect.value = "";
        if (sourceSelect) sourceSelect.value = "";
        if (profitSelect) profitSelect.value = "";
        applyFilters();
    }

    form.addEventListener("submit", (event) => {
        event.preventDefault();
        applyFilters();
    });
    keywordInput?.addEventListener("input", applyFilters);
    statusSelect?.addEventListener("change", applyFilters);
    sourceSelect?.addEventListener("change", applyFilters);
    profitSelect?.addEventListener("change", applyFilters);
    clearButton?.addEventListener("click", clearFilters);

    applyFilters();
})();
