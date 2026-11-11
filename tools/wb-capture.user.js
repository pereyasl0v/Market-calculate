// ==UserScript==
// @name         Market Calculate — экспорт ТОП-10 Wildberries
// @namespace    https://github.com/pereyasl0v/Market-calculate
// @version      0.1.0
// @description  Сохраняет первые 10 товаров из обычного поискового ответа WB в локальный JSON, без cookies.
// @match        https://www.wildberries.ru/*
// @run-at       document-start
// @grant        none
// ==/UserScript==
(() => {
  "use strict";
  let latest = null;
  let button;

  const toQuery = value => {
    let s = String(value || "").replace(/\+/g, " ");
    for (let i = 0; i < 2 && /%[0-9a-f]{2}/i.test(s); i++) {
      try { s = decodeURIComponent(s); } catch { break; }
    }
    return s.trim();
  };
  const isSearch = input => {
    try {
      const u = new URL(String(input), location.href);
      if (!/\/(?:__internal\/u-search\/)?exactmatch\/ru\/common\/v\d+\/search$/i.test(u.pathname)) return null;
      const page = u.searchParams.get("page");
      if (page && page !== "1") return null;
      return {query:toQuery(u.searchParams.get("query")), priority:page ? 1 : 2};
    } catch { return null; }
  };
  const rub = cents => {
    const n = Number(cents);
    return cents == null || !Number.isFinite(n) || n <= 0 ? null : Math.round(n) / 100;
  };
  function processResponse(url, data) {
    const candidate = isSearch(url);
    if (!candidate?.query) return;
    const cards = data?.products ?? data?.data?.products;
    if (!Array.isArray(cards) || !cards.length) return;
    const products = cards.slice(0, 10).map((p, index) => {
      const price = p.sizes?.find(s => s?.price?.product != null)?.price
        || p.sizes?.find(s => s?.price)?.price || {};
      return {
        position:index+1,
        id:String(p.id ?? p.nmId ?? ""),
        name:String(p.name ?? "Без названия"),
        brand:String(p.brand ?? ""),
        price_rub:rub(price.product ?? p.salePriceU),
        basic_price_rub:rub(price.basic ?? p.priceU)
      };
    }).filter(p => p.id && p.price_rub !== null);
    if (!products.length) return;
    if (latest?.query === candidate.query && latest.priority > candidate.priority) return;
    latest = {
      query:candidate.query,
      products,
      priority:candidate.priority,
      captured_at:new Date().toISOString()
    };
    if (button) {
      button.disabled=false;
      button.textContent="↓ Сохранить ТОП-10 ("+products.length+")";
      button.title="Поиск: "+candidate.query;
    }
  }

  const nativeFetch=window.fetch;
  if (typeof nativeFetch === "function") {
    window.fetch=async function(...args) {
      const response=await nativeFetch.apply(this,args);
      const url=args[0] instanceof Request ? args[0].url : String(args[0]);
      if (isSearch(url) && response.ok) {
        response.clone().json().then(json=>processResponse(url,json)).catch(()=>{});
      }
      return response;
    };
  }

  const oldOpen=XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open=function(method,url,...args) {
    this.__mcURL=String(url);
    return oldOpen.call(this,method,url,...args);
  };
  const oldSend=XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.send=function(...args) {
    if (isSearch(this.__mcURL)) {
      this.addEventListener("load",function(){
        if (this.status<200 || this.status>=300) return;
        try {
          const data=this.responseType==="json" ? this.response : JSON.parse(this.responseText);
          processResponse(this.__mcURL,data);
        }catch{}
      },{once:true});
    }
    return oldSend.apply(this,args);
  };

  function installButton() {
    if (!document.body || document.getElementById("mc-wb-export")) return;
    button=document.createElement("button");
    button.id="mc-wb-export";
    button.disabled=!latest;
    button.textContent=latest?"↓ Сохранить ТОП-10 ("+latest.products.length+")":"Откройте поиск WB";
    button.style.cssText="position:fixed;right:16px;bottom:16px;z-index:2147483640;padding:12px 16px;border:0;border-radius:12px;background:#6a21d8;color:#fff;font:600 14px Arial;box-shadow:0 4px 20px #3335;cursor:pointer";
    button.addEventListener("click",()=>{
      if (!latest) return;
      // Only sanitized product fields are exported. No request headers, cookies, tokens or HAR.
      const sanitized={source:"market-calculate-browser",query:latest.query,captured_at:latest.captured_at,products:latest.products};
      const blob=new Blob([JSON.stringify(sanitized,null,2)],{type:"application/json"});
      const url=URL.createObjectURL(blob);
      const a=document.createElement("a");
      a.href=url;a.download="wb-top10-"+Date.now()+".json";a.click();
      setTimeout(()=>URL.revokeObjectURL(url),1000);
    });
    document.body.appendChild(button);
  }
  if (document.readyState==="loading") document.addEventListener("DOMContentLoaded",installButton,{once:true});
  else installButton();
})();
