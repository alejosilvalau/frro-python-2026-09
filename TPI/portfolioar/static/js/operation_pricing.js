(() => {
  const form = document.querySelector('[data-operation-pricing]');
  if (!form) return;

  const apiUrl = form.dataset.pricingApi;
  const stockInput = document.getElementById(form.dataset.stockInput);
  const dateInput = document.getElementById(form.dataset.dateInput);
  const arsInput = document.getElementById('price_ars');
  const usdInput = document.getElementById('price_usd');
  const priceInput = document.getElementById('price');
  const inputCurrency = document.getElementById('price_input_currency');
  const cclInput = document.getElementById('client_ccl_rate');
  const manualCcl = document.getElementById('manual_ccl_rate');
  const cclStatus = document.getElementById('ccl-badge');
  const priceStatus = document.getElementById('price-status');
  const submitButton = form.querySelector('button[type="submit"], button:not([type])');
  const purchaseForm = form.hasAttribute('data-purchase-check');
  const purchaseWarning = document.getElementById('purchase-warning');
  const brokerInput = document.getElementById(form.dataset.brokerInput);
  let quoteUnit = 1;
  let requestId = 0;
  let controller;
  let cclRate;
  let pricingBlocked = false;

  const updateTotal = () => {
    const amount = Number(document.getElementById('amount')?.value);
    const paymentInput = form.querySelector('input[name="purchase_currency"], input[name="sell_currency"]:checked');
    const payment = paymentInput?.value;
    const price = Number(payment === 'USD' ? usdInput.value : arsInput.value);
    const total = document.getElementById('operation-total');
    const hasTotal = amount > 0 && price > 0 && Number.isFinite(amount * price) && (!purchaseForm || Boolean(payment));
    const value = amount * price / quoteUnit;
    if (total) {
      total.classList.toggle('d-none', !hasTotal);
      if (hasTotal) total.querySelector('strong').textContent = `${payment === 'USD' ? 'U$D ' : '$'}${value.toLocaleString('es-AR', {minimumFractionDigits: 2})}`;
    }
    if (!purchaseForm) return;

    const stockReady = Boolean(stockInput?.value || form.dataset.stockId);
    const brokerReady = !brokerInput || Boolean(brokerInput.value);
    const available = Number(payment === 'USD' ? paymentInput?.dataset.availableUsd : paymentInput?.dataset.availableArs);
    const insufficient = hasTotal && Number.isFinite(available) && value > available + 0.0000001;
    if (purchaseWarning) {
      const liquidityLink = purchaseWarning.querySelector('a');
      purchaseWarning.classList.toggle('d-none', !insufficient && (brokerReady || !stockReady));
      liquidityLink?.classList.toggle('d-none', !insufficient);
      if (insufficient) {
        const missing = value - available;
        const symbol = payment === 'USD' ? 'U$D ' : '$';
        purchaseWarning.querySelector('span').textContent = `Liquidez ${payment} insuficiente: faltan ${symbol}${missing.toLocaleString('es-AR', {minimumFractionDigits: 2})}.`;
      } else if (stockReady && !brokerReady) {
        purchaseWarning.querySelector('span').textContent = 'Elegí un broker para continuar.';
      }
    }
    if (submitButton) submitButton.disabled = pricingBlocked || !stockReady || !payment || !brokerReady || !hasTotal || insufficient || !priceInput.value;
  };

  const currentCurrency = () => document.querySelector('input[name="price_editor_currency"]:checked')?.value || 'ARS';
  const setEditableCurrency = () => {
    const currency = currentCurrency();
    arsInput.readOnly = currency !== 'ARS';
    usdInput.readOnly = currency !== 'USD';
    inputCurrency.value = currency;
    syncHiddenPrice();
    updateTotal();
  };
  const syncHiddenPrice = () => {
    priceInput.value = currentCurrency() === 'ARS' ? arsInput.value : usdInput.value;
  };
  const reset = () => {
    requestId += 1;
    if (controller) controller.abort();
    cclRate = null;
    quoteUnit = 1;
    arsInput.value = '';
    usdInput.value = '';
    priceInput.value = '';
    cclInput.value = '';
    manualCcl?.closest('.mb-3').classList.add('d-none');
    pricingBlocked = false;
    if (submitButton && !purchaseForm) submitButton.disabled = false;
    if (cclStatus) cclStatus.textContent = '';
    if (priceStatus) priceStatus.textContent = '';
    updateTotal();
  };
  const deriveOther = () => {
    if (!cclRate) return;
    const source = currentCurrency() === 'ARS' ? arsInput : usdInput;
    const target = currentCurrency() === 'ARS' ? usdInput : arsInput;
    const value = Number(source.value);
    if (value > 0) target.value = (currentCurrency() === 'ARS' ? value / cclRate : value * cclRate).toFixed(4);
    syncHiddenPrice();
    updateTotal();
  };
  const load = () => {
    const stockId = stockInput?.value || form.dataset.stockId;
    const date = dateInput?.value?.slice(0, 10);
    reset();
    if (!stockId || !date) return;
    const id = requestId;
    controller = new AbortController();
    fetch(`${apiUrl}?stock_id=${stockId}&fecha=${date}`, {signal: controller.signal})
      .then(response => response.json().then(data => ({response, data})))
      .then(({response, data}) => {
        if (id !== requestId) return;
        if (!response.ok) {
          pricingBlocked = true;
          if (submitButton && !purchaseForm) submitButton.disabled = true;
          if (priceStatus) priceStatus.textContent = data.error === 'dia_no_habil' ? `Día no hábil. Último hábil: ${data.last_business_day}` : 'Fecha inválida';
          updateTotal();
          return;
        }
        quoteUnit = data.quote_unit || 1;
        pricingBlocked = false;
        if (submitButton && !purchaseForm) submitButton.disabled = false;
        cclRate = data.ccl?.rate ? Number(data.ccl.rate) : null;
        if (cclRate) {
          cclInput.value = cclRate;
          if (cclStatus) cclStatus.textContent = `CCL ${data.ccl.source} ${data.ccl.ccl_date}: $${cclRate.toLocaleString('es-AR')}`;
        } else if (manualCcl) {
          manualCcl.closest('.mb-3').classList.remove('d-none');
          if (cclStatus) cclStatus.textContent = 'CCL no disponible: ingresalo manualmente';
        }
        if (data.prices) {
          arsInput.value = data.prices.ARS || '';
          usdInput.value = data.prices.USD || '';
          if (priceStatus) priceStatus.textContent = data.quote ? `Automático · ${data.quote.source}` : 'Precio manual';
        }
        setEditableCurrency();
        updateTotal();
      }).catch(error => { if (error.name !== 'AbortError' && priceStatus) priceStatus.textContent = 'No se pudo consultar la cotización'; });
  };

  stockInput?.addEventListener('change', load);
  dateInput?.addEventListener('change', load);
  document.querySelectorAll('input[name="price_editor_currency"]').forEach(input => input.addEventListener('change', setEditableCurrency));
  arsInput.addEventListener('input', () => { if (currentCurrency() === 'ARS') deriveOther(); });
  usdInput.addEventListener('input', () => { if (currentCurrency() === 'USD') deriveOther(); });
  manualCcl?.addEventListener('input', () => {
    const rate = Number(manualCcl.value);
    if (rate > 0) {
      cclRate = rate;
      cclInput.value = rate;
      deriveOther();
    }
  });
  document.getElementById('amount')?.addEventListener('input', updateTotal);
  brokerInput?.addEventListener('change', updateTotal);
  document.querySelectorAll('input[name="purchase_currency"], input[name="sell_currency"]').forEach(input => input.addEventListener('change', updateTotal));
  setEditableCurrency();
  if (form.dataset.stockId) load();
})();
