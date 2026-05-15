(function () {
    const form = document.querySelector("[data-pricing-form]");
    if (!form) return;

    const priceNode = document.getElementById("price-data");
    const prices = priceNode ? JSON.parse(priceNode.textContent || "[]") : [];
    const quotePreview = document.querySelector("[data-quote-preview]");
    const costPreview = document.querySelector("[data-cost-preview]");
    const customerSelect = form.querySelector("[data-customer-select]");
    const customerHistoryPanel = document.querySelector("[data-customer-history]");
    const customerHistoryMatch = document.querySelector("[data-history-match]");
    const customerHistoryList = document.querySelector("[data-history-list]");
    let historyTimer = null;

    function field(name) {
        return form.querySelector(`[data-field="${name}"]`);
    }

    function value(name, fallback = 0) {
        const el = field(name);
        if (!el || el.value === "") return fallback;
        const number = Number(el.value);
        return Number.isFinite(number) ? number : fallback;
    }

    function money(number) {
        return `¥${Number(number || 0).toFixed(2)}`;
    }

    function ratePercent(number) {
        return `${Number(number || 0).toFixed(2)}%`;
    }

    function findPrice() {
        const specification = field("specification")?.value.trim();
        const thickness = field("thickness")?.value.trim();
        return prices.find((item) => item.specification === specification && item.thickness === thickness);
    }

    function renderPreview(node, rows) {
        if (!node) return;
        node.innerHTML = `<dl>${rows.map(([label, val]) => `<dt>${label}</dt><dd>${val}</dd>`).join("")}</dl>`;
    }

    function escapeHtml(value) {
        return String(value ?? "").replace(/[&<>"']/g, (char) => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;",
        }[char]));
    }

    function renderOrderRows(order, includeProfit) {
        const rows = [
            ["订单", order.order_no],
            ["产品", order.product_name || "-"],
            ["规格厚度", `${order.specification} / ${order.thickness}`],
            ["成交价", money(order.final_quote)],
            ["数量", order.quantity ?? "-"],
        ];
        if (includeProfit && Object.prototype.hasOwnProperty.call(order, "profit")) {
            rows.push(["利润", money(order.profit)]);
        }
        rows.push(["下单时间", (order.created_at || "").slice(0, 16) || "-"]);
        return rows
            .map(([label, val]) => `<div class="history-price-row"><span>${escapeHtml(label)}</span><strong>${escapeHtml(val)}</strong></div>`)
            .join("");
    }

    async function renderCustomerHistory() {
        if (!customerSelect || !customerHistoryPanel) return;
        const customerId = customerSelect.value;
        if (!customerId) {
            customerHistoryPanel.hidden = true;
            return;
        }
        const specification = encodeURIComponent(field("specification")?.value.trim() || "");
        const thickness = encodeURIComponent(field("thickness")?.value.trim() || "");
        try {
            const response = await fetch(`/customers/${customerId}/price-history?specification=${specification}&thickness=${thickness}`, {
                headers: { Accept: "application/json" },
            });
            if (!response.ok) throw new Error("history request failed");
            const payload = await response.json();
            const includeProfit = Boolean(payload.can_view_profit);
            customerHistoryPanel.hidden = false;

            if (customerHistoryMatch) {
                if (payload.matching_order) {
                    const profitLine = includeProfit && Object.prototype.hasOwnProperty.call(payload.matching_order, "profit")
                        ? `<span>上次利润：${money(payload.matching_order.profit)}</span>`
                        : "";
                    customerHistoryMatch.innerHTML = `
                        <div class="history-price-highlight">
                            <strong>历史成交价：${money(payload.matching_order.final_quote)}</strong>
                            <span>上次数量：${escapeHtml(payload.matching_order.quantity ?? "-")}</span>
                            ${profitLine}
                            <span>上次下单时间：${escapeHtml((payload.matching_order.created_at || "").slice(0, 16) || "-")}</span>
                        </div>
                    `;
                } else {
                    customerHistoryMatch.innerHTML = `<p class="hint">该客户暂无相同规格和厚度的历史成交价。</p>`;
                }
            }

            if (customerHistoryList) {
                if (!payload.orders.length) {
                    customerHistoryList.innerHTML = `<p class="empty">该客户暂无历史订单。</p>`;
                } else {
                    customerHistoryList.innerHTML = payload.orders
                        .map((order) => `<article class="history-price-card">${renderOrderRows(order, includeProfit)}</article>`)
                        .join("");
                }
            }
        } catch (error) {
            customerHistoryPanel.hidden = false;
            if (customerHistoryMatch) {
                customerHistoryMatch.innerHTML = `<p class="message error">历史价格读取失败，请刷新页面后重试。</p>`;
            }
            if (customerHistoryList) customerHistoryList.innerHTML = "";
        }
    }

    function queueCustomerHistoryRender() {
        if (historyTimer) window.clearTimeout(historyTimer);
        historyTimer = window.setTimeout(renderCustomerHistory, 150);
    }

    function applySelectedCustomer() {
        if (!customerSelect) return;
        const selected = customerSelect.selectedOptions[0];
        if (!selected || !customerSelect.value) {
            queueCustomerHistoryRender();
            return;
        }
        const customerNameInput = form.querySelector('[name="customer_name"]');
        const customerContactInput = form.querySelector('[name="customer_contact"]');
        const sourceInput = form.querySelector('[name="source"]');
        if (customerNameInput && selected.dataset.name) customerNameInput.value = selected.dataset.name;
        if (customerContactInput && selected.dataset.contact) customerContactInput.value = selected.dataset.contact;
        if (sourceInput && selected.dataset.source) sourceInput.value = selected.dataset.source;
        queueCustomerHistoryRender();
    }

    function recalc() {
        const price = findPrice();
        if (price) {
            const saleUnitInput = field("sale_unit_price");
            const costUnitInput = field("cost_unit_price");
            if (saleUnitInput) saleUnitInput.value = Number(price.sale_price).toFixed(2);
            if (costUnitInput) costUnitInput.value = Number(price.cost_price).toFixed(2);
        }

        const saleUnitPrice = value("sale_unit_price");
        const costUnitPrice = value("cost_unit_price");
        const boardCount = value("board_count", 1);
        const materialQuote = saleUnitPrice * boardCount;
        const cuttingFee = value("cutting_length") * value("cutting_unit_price", 12);
        const holeFee = value("hole_count") * value("hole_unit_price", 2);
        const chamferFee = value("chamfer_count") * value("chamfer_unit_price", 3);
        const subtotal = materialQuote + cuttingFee + holeFee + chamferFee + value("polishing_fee") + value("packaging_fee", 50) + value("shipping_fee") + value("other_fee");
        const urgentFee = field("is_urgent")?.value === "1" ? subtotal * value("urgent_rate", 0.2) : 0;
        const taxFee = field("include_tax")?.value === "1" ? subtotal * value("tax_rate", 0.13) : 0;
        const quoteTotal = Math.max(300, subtotal + urgentFee + taxFee);
        const finalQuoteInput = field("final_quote");
        if (finalQuoteInput && !finalQuoteInput.value) {
            finalQuoteInput.value = quoteTotal.toFixed(2);
        }
        const finalQuote = value("final_quote", quoteTotal);

        const materialCost = costUnitPrice * boardCount;
        const totalCost = materialCost + value("labor_cost") + value("machine_cost") + value("packaging_cost") + value("shipping_cost") + value("platform_fee") + value("other_cost");
        const profit = finalQuote - totalCost;
        const marginRate = finalQuote > 0 ? (profit / finalQuote) * 100 : 0;

        renderPreview(quotePreview, [
            ["板材报价", money(materialQuote)],
            ["切割费", money(cuttingFee)],
            ["打孔费", money(holeFee)],
            ["倒角费", money(chamferFee)],
            ["报价小计", money(subtotal)],
            ["加急费", money(urgentFee)],
            ["税费", money(taxFee)],
            ["自动报价", money(quoteTotal)],
        ]);
        renderPreview(costPreview, [
            ["板材成本", money(materialCost)],
            ["总成本", money(totalCost)],
            ["利润", money(profit)],
            ["毛利率", ratePercent(marginRate)],
        ]);
        queueCustomerHistoryRender();
    }

    form.addEventListener("input", recalc);
    form.addEventListener("change", recalc);
    if (customerSelect) {
        customerSelect.addEventListener("change", applySelectedCustomer);
    }
    recalc();
    renderCustomerHistory();
})();
