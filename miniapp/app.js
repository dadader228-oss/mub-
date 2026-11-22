const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
  try { tg.setHeaderColor("#0B0B10"); tg.setBackgroundColor("#0B0B10"); } catch (_) {}
}

const API = (location.protocol === "file:" || location.hostname === "localhost" || location.hostname === "127.0.0.1")
  ? "http://127.0.0.1:8000/api"
  : "/api";

function getInitData() { return tg?.initData || ""; }

async function api(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    "X-Telegram-Init-Data": getInitData(),
    ...(options.headers || {}),
  };
  const res = await fetch(`${API}${path}`, { ...options, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try { const j = await res.json(); detail = j.detail || detail; } catch (_) {}
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json();
}

function toast(msg, ms = 2500) {
  const el = document.getElementById("toast");
  if (!el) return;
  el.textContent = msg;
  el.classList.remove("hidden");
  setTimeout(() => el.classList.add("hidden"), ms);
}

function escapeHtml(s) {
  return String(s ?? "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

document.querySelectorAll(".nav-item").forEach((btn) => {
  btn.addEventListener("click", () => {
    const page = btn.dataset.page;
    document.querySelectorAll(".nav-item").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".page").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(page)?.classList.add("active");
    if (page === "catalog") loadCatalog();
    if (page === "orders") loadOrders();
    if (page === "profile") loadProfile();
    if (page === "cart") loadCart();
    if (page === "support") loadTickets();
  });
});

function productCard(p) {
  const img = p.image_url
    ? `<img src="${escapeHtml(p.image_url)}" alt="" loading="lazy" />`
    : `<div class="img-placeholder">🤖</div>`;
  return `<div class="product-card" data-id="${p.id}">${img}<div class="body"><div class="name">${escapeHtml(p.name)}</div><div class="price">${p.price_stars} ⭐ <span>/ ${p.price_rub} ₽</span></div></div></div>`;
}

async function loadHome() {
  try {
    const [products, categories, news] = await Promise.all([
      api("/products?featured=true").catch(() => []),
      api("/categories").catch(() => []),
      api("/products?is_new=true").catch(() => []),
    ]);
    const feat = document.getElementById("featured-products");
    if (feat) feat.innerHTML = products.slice(0, 6).map(productCard).join("") || "<p class='muted'>Нет товаров. Запустите seed.</p>";
    const cats = document.getElementById("categories");
    if (cats) cats.innerHTML = categories.map((c) =>
      `<button class="cat-chip" data-slug="${escapeHtml(c.slug)}">${c.icon || ""} ${escapeHtml(c.name)}</button>`
    ).join("") || "";
    const newsEl = document.getElementById("new-products");
    if (newsEl) newsEl.innerHTML = news.slice(0, 4).map(productCard).join("");
  } catch (e) {
    console.error(e);
    const feat = document.getElementById("featured-products");
    if (feat) feat.innerHTML = "<p class='muted'>Не удалось загрузить. Проверьте API.</p>";
  }
}

async function loadCatalog(q = "", category = "") {
  try {
    let path = "/products?";
    if (q) path += `q=${encodeURIComponent(q)}&`;
    if (category) path += `category=${encodeURIComponent(category)}&`;
    const products = await api(path);
    const el = document.getElementById("catalog-products");
    if (el) el.innerHTML = products.map(productCard).join("") || "<p class='muted'>Ничего не найдено</p>";
  } catch (e) { toast("Ошибка каталога"); }
}

document.getElementById("search")?.addEventListener("input", (e) => {
  clearTimeout(window._searchT);
  window._searchT = setTimeout(() => loadCatalog(e.target.value.trim()), 300);
});

document.getElementById("categories")?.addEventListener("click", (e) => {
  const chip = e.target.closest(".cat-chip");
  if (!chip) return;
  document.querySelectorAll(".nav-item").forEach((b) => b.classList.remove("active"));
  document.querySelectorAll(".page").forEach((p) => p.classList.remove("active"));
  document.querySelector('[data-page="catalog"]')?.classList.add("active");
  document.getElementById("catalog")?.classList.add("active");
  loadCatalog("", chip.dataset.slug);
});

async function loadOrders() {
  try {
    const orders = await api("/orders");
    const el = document.getElementById("orders-list");
    if (!el) return;
    if (!orders.length) { el.innerHTML = "<p class='muted'>Заказов пока нет</p>"; return; }
    el.innerHTML = orders.map((o) =>
      `<div class="item"><strong>${escapeHtml(o.order_number)}</strong><div>${o.total_stars} ⭐ / ${o.total_rub} ₽</div><div class="status">${escapeHtml(o.status)}</div></div>`
    ).join("");
  } catch (e) { toast("Ошибка заказов"); }
}

async function loadCart() {
  try {
    const cart = await api("/cart");
    const el = document.getElementById("cart-list");
    if (!el) return;
    if (!cart.items.length) {
      el.innerHTML = "<p class='muted'>Корзина пуста</p>";
      document.getElementById("cart-actions")?.classList.add("hidden");
      return;
    }
    el.innerHTML = cart.items.map((i) =>
      `<div class="item"><strong>${escapeHtml(i.name)}</strong><div>${i.quantity} × ${i.price_stars}⭐ / ${i.price_rub}₽</div><button class="btn-sm" data-remove="${i.product_id}">Убрать</button></div>`
    ).join("");
    const total = document.getElementById("cart-total");
    if (total) total.textContent = `${cart.total_stars} ⭐ / ${cart.total_rub} ₽`;
    document.getElementById("cart-actions")?.classList.remove("hidden");
  } catch (e) { toast("Ошибка корзины"); }
}

async function loadProfile() {
  try {
    const me = await api("/me");
    const el = document.getElementById("profile-data");
    if (el) el.innerHTML = `<p><strong>ID:</strong> ${me.telegram_id}</p><p><strong>Имя:</strong> ${escapeHtml(me.first_name || "—")}</p><p><strong>Username:</strong> @${escapeHtml(me.username || "—")}</p><p><strong>Баланс:</strong> ${me.balance} ₽</p><p class="muted" style="margin-top:8px">Регистрация: ${me.created_at ? new Date(me.created_at).toLocaleDateString() : "—"}</p>${me.is_admin ? "<p style='color:var(--purple);margin-top:8px'>🛠 Администратор</p>" : ""}`;
  } catch (e) {
    const el = document.getElementById("profile-data");
    if (el) el.innerHTML = "<p class='muted'>Откройте Mini App внутри Telegram</p>";
  }
}

async function loadTickets() {
  try {
    const tickets = await api("/tickets");
    const el = document.getElementById("tickets-list");
    if (!el) return;
    if (!tickets.length) { el.innerHTML = "<p class='muted'>Обращений нет</p>"; return; }
    el.innerHTML = tickets.map((t) =>
      `<div class="item"><strong>${escapeHtml(t.ticket_number)}</strong> — ${escapeHtml(t.subject)}<div class="status">${escapeHtml(t.status)}</div></div>`
    ).join("");
  } catch (_) {}
}

document.addEventListener("click", async (e) => {
  const card = e.target.closest(".product-card");
  if (card) {
    try {
      await api("/cart/add", { method: "POST", body: JSON.stringify({ product_id: Number(card.dataset.id), quantity: 1 }) });
      toast("Добавлено в корзину");
      if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
    } catch (err) { toast(err.message || "Ошибка"); }
    return;
  }
  const rem = e.target.closest("[data-remove]");
  if (rem) {
    try {
      await api("/cart/remove", { method: "POST", body: JSON.stringify({ product_id: Number(rem.dataset.remove), quantity: 1 }) });
      toast("Удалено"); loadCart();
    } catch (err) { toast(err.message || "Ошибка"); }
  }
});

document.getElementById("btn-checkout-stars")?.addEventListener("click", async () => {
  try {
    const order = await api("/orders", { method: "POST", body: JSON.stringify({ payment_method: "stars" }) });
    toast(`Заказ ${order.order_number} создан. Оплатите Stars в боте (/pay от админа или автоматизация).`);
  } catch (e) { toast(e.message || "Ошибка"); }
});

document.getElementById("btn-checkout-rub")?.addEventListener("click", async () => {
  try {
    const order = await api("/orders", { method: "POST", body: JSON.stringify({ payment_method: "rub" }) });
    let instr = "Ожидайте инструкции.";
    try { const s = await api("/settings/payment_instructions"); instr = s.text || instr; } catch (_) {}
    toast(`Заказ ${order.order_number}. ${instr}`);
    loadOrders();
  } catch (e) { toast(e.message || "Ошибка"); }
});

document.getElementById("btn-new-ticket")?.addEventListener("click", async () => {
  const subject = prompt("Тема обращения:");
  if (!subject) return;
  const text = prompt("Описание:");
  if (!text) return;
  try {
    const t = await api("/tickets", { method: "POST", body: JSON.stringify({ category: "other", subject, text }) });
    toast(`Тикет ${t.ticket_number} создан`);
    loadTickets();
  } catch (e) { toast(e.message || "Ошибка"); }
});

loadHome();
if (tg?.initDataUnsafe?.user) {
  const ui = document.getElementById("user-info");
  if (ui) ui.textContent = tg.initDataUnsafe.user.first_name || "";
}
