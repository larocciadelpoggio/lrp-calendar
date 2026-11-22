/* Villa La Roccia del Poggio - availability & price calendar widget.
   Prices are not shown per night: the total appears once the guest picks dates.
   Embed:  <div id="lrp-calendar" data-lang="en"></div>
           <script src="https://YOUR-NAME.github.io/lrp-calendar/calendar.js" defer></script>
*/
(function () {
  "use strict";
  var script = document.currentScript;
  var BASE = script ? script.src.replace(/[^\/]*$/, "") : "";

  var T = {
    en: {
      months: ["January","February","March","April","May","June","July","August","September","October","November","December"],
      days: ["Mo","Tu","We","Th","Fr","Sa","Su"],
      title: "Availability & prices", intro: "Select your dates to see the price of your stay.", checkin: "Check-in", checkout: "Check-out", guests: "Guests",
      pickIn: "Select your arrival date", pickOut: "Now select your departure date",
      nights: function (n) { return n + (n === 1 ? " night" : " nights"); },
      perNight: "per night", from: "from", minStay: function (n) { return "Minimum stay " + n + (n === 1 ? " night" : " nights"); },
      accommodation: "Accommodation", extra: function (g, f) { return "Extra guests (" + g + " × " + f + " / night)"; },
      total: "Estimated total", request: "Request booking by email", clear: "Clear",
      errMin: function (n) { return "Minimum stay from this date is " + n + " nights."; },
      errBusy: "Some nights in this range are not available.", errNoPrice: "Prices not yet published for some of these nights.",
      legendFree: "Available", legendBusy: "Not available", legendSel: "Your stay",
      loading: "Loading calendar…", failed: "The calendar could not be loaded. Please contact us by email.",
      updated: "Updated", onRequest: "on request",
      subject: "Booking request", body: function (s) {
        return "Hello,\n\nI would like to book " + s.prop + ":\n\nCheck-in: " + s.inD + "\nCheck-out: " + s.outD +
          "\nNights: " + s.n + "\nGuests: " + s.g + "\nEstimated total: " + s.tot + "\n\nName:\nPhone:\n\nThank you!";
      }
    },
    it: {
      months: ["Gennaio","Febbraio","Marzo","Aprile","Maggio","Giugno","Luglio","Agosto","Settembre","Ottobre","Novembre","Dicembre"],
      days: ["Lu","Ma","Me","Gi","Ve","Sa","Do"],
      title: "Disponibilità e prezzi", intro: "Seleziona le date per vedere il prezzo del soggiorno.", checkin: "Arrivo", checkout: "Partenza", guests: "Ospiti",
      pickIn: "Seleziona la data di arrivo", pickOut: "Ora seleziona la data di partenza",
      nights: function (n) { return n + (n === 1 ? " notte" : " notti"); },
      perNight: "a notte", from: "da", minStay: function (n) { return "Soggiorno minimo " + n + (n === 1 ? " notte" : " notti"); },
      accommodation: "Soggiorno", extra: function (g, f) { return "Ospiti aggiuntivi (" + g + " × " + f + " / notte)"; },
      total: "Totale stimato", request: "Richiedi prenotazione via email", clear: "Annulla",
      errMin: function (n) { return "Da questa data il soggiorno minimo è di " + n + " notti."; },
      errBusy: "Alcune notti di questo periodo non sono disponibili.", errNoPrice: "Prezzi non ancora pubblicati per alcune di queste notti.",
      legendFree: "Disponibile", legendBusy: "Non disponibile", legendSel: "Il tuo soggiorno",
      loading: "Caricamento calendario…", failed: "Impossibile caricare il calendario. Contattaci via email.",
      updated: "Aggiornato", onRequest: "su richiesta",
      subject: "Richiesta di prenotazione", body: function (s) {
        return "Buongiorno,\n\nvorrei prenotare " + s.prop + ":\n\nArrivo: " + s.inD + "\nPartenza: " + s.outD +
          "\nNotti: " + s.n + "\nOspiti: " + s.g + "\nTotale stimato: " + s.tot + "\n\nNome:\nTelefono:\n\nGrazie!";
      }
    }
  };

  var CSS = "" +
    ".lrp{font-family:Montserrat,Arial,sans-serif;color:#1d1d1d;max-width:900px;margin:0 auto;box-sizing:border-box}" +
    ".lrp *{box-sizing:border-box}" +
    ".lrp h3{font-size:24px;font-weight:600;margin:0 0 6px}" +
    ".lrp .lrp-sub{font-size:13px;color:#666;margin:0 0 16px}" +
    ".lrp-wrap{display:flex;gap:24px;flex-wrap:wrap}" +
    ".lrp-cal{flex:2 1 520px;min-width:0}" +
    ".lrp-side{flex:1 1 240px;border:1px solid #e3e3e3;border-radius:12px;padding:16px;align-self:flex-start;background:#fff}" +
    ".lrp-nav{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}" +
    ".lrp-nav button{border:1px solid #ddd;background:#fff;border-radius:50%;width:34px;height:34px;cursor:pointer;font-size:16px}" +
    ".lrp-nav button:disabled{opacity:.3;cursor:default}" +
    ".lrp-months{display:flex;gap:20px}" +
    ".lrp-month{flex:1 1 0;min-width:0}" +
    ".lrp-month h4{text-align:center;font-size:15px;font-weight:600;margin:4px 0 8px}" +
    ".lrp-grid{display:grid;grid-template-columns:repeat(7,1fr);gap:2px}" +
    ".lrp-dow{font-size:11px;color:#888;text-align:center;padding:4px 0}" +
    ".lrp-d{border:0;background:#f4f8f4;border-radius:6px;padding:0;text-align:center;cursor:pointer;min-height:38px;font:inherit;color:inherit}" +
    ".lrp-d .n{display:block;font-size:13px;font-weight:600}" +
    ".lrp-d .p{display:block;font-size:10px;color:#2f6f3e;margin-top:1px}" +
    ".lrp-d.empty{background:transparent;cursor:default}" +
    ".lrp-d.off{background:#f2f2f2;color:#b5b5b5;cursor:default}" +
    ".lrp-d.busy{background:#f2f2f2;color:#b5b5b5;text-decoration:line-through}" +
    ".lrp-d.busy .p,.lrp-d.off .p{color:#c4c4c4}" +
    ".lrp-d.co{cursor:pointer}" +
    ".lrp-d.sel,.lrp-d.edge{background:#1d1d1d;color:#fff}" +
    ".lrp-d.sel .p,.lrp-d.edge .p{color:#ddd}" +
    ".lrp-d.range{background:#cfe3d3}" +
    ".lrp-d:not(.off):not(.empty):not(.busy):hover{outline:2px solid #1d1d1d}" +
    ".lrp-legend{display:flex;gap:14px;font-size:11px;color:#666;margin-top:10px;flex-wrap:wrap}" +
    ".lrp-legend i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:4px;vertical-align:-2px}" +
    ".lrp-row{display:flex;justify-content:space-between;font-size:13px;margin:6px 0;gap:8px}" +
    ".lrp-row b{font-weight:600}" +
    ".lrp-tot{border-top:1px solid #e3e3e3;margin-top:10px;padding-top:10px;font-size:15px}" +
    ".lrp-msg{font-size:12px;color:#b3261e;margin:8px 0;min-height:16px}" +
    ".lrp-hint{font-size:13px;color:#444;margin:0 0 10px}" +
    ".lrp-note{font-size:11px;color:#777;margin-top:10px;line-height:1.4}" +
    ".lrp select{font:inherit;padding:4px 6px;border-radius:6px;border:1px solid #ccc}" +
    ".lrp-btn{display:block;width:100%;margin-top:12px;background:#1d1d1d;color:#fff;border:0;border-radius:24px;padding:12px;font:inherit;font-weight:600;cursor:pointer;text-align:center;text-decoration:none}" +
    ".lrp-btn[aria-disabled=true]{opacity:.35;pointer-events:none}" +
    ".lrp-link{background:none;border:0;color:#555;text-decoration:underline;cursor:pointer;font:inherit;font-size:12px;padding:0;margin-top:8px}" +
    ".lrp-upd{font-size:10px;color:#aaa;margin-top:8px}" +
    "@media (max-width:640px){.lrp-months .lrp-month:nth-child(2){display:none}.lrp-side{flex-basis:100%}}";

  function pad(n) { return (n < 10 ? "0" : "") + n; }
  function iso(d) { return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()); }
  function parse(s) { var a = s.split("-"); return new Date(+a[0], +a[1] - 1, +a[2]); }
  function addDays(d, n) { var x = new Date(d); x.setDate(x.getDate() + n); return x; }

  function init(el) {
    var lang = (el.getAttribute("data-lang") || document.documentElement.lang || "en").slice(0, 2).toLowerCase();
    var t = T[lang] || T.en;
    var src = el.getAttribute("data-src") || (BASE + "availability.json");
    if (!document.getElementById("lrp-css")) {
      var st = document.createElement("style"); st.id = "lrp-css"; st.textContent = CSS; document.head.appendChild(st);
    }
    el.className = (el.className + " lrp").trim();
    el.innerHTML = "<p class='lrp-sub'>" + t.loading + "</p>";

    fetch(src + (src.indexOf("?") < 0 ? "?" : "&") + "t=" + Math.floor(Date.now() / 600000), { cache: "no-store" })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (data) { render(el, t, lang, data); })
      .catch(function () { el.innerHTML = "<p class='lrp-sub'>" + t.failed + "</p>"; });
  }

  function render(el, t, lang, data) {
    var busy = {}; (data.unavailable || []).forEach(function (d) { busy[d] = 1; });
    var days = data.days || {};
    var cur = data.currency === "EUR" ? "€" : (data.currency + " ");
    function money(v) { return cur + Math.round(v).toLocaleString(lang === "it" ? "it-IT" : "en-GB"); }
    var today = new Date(); today.setHours(0, 0, 0, 0);
    var keys = Object.keys(days).sort();
    var lastPriced = keys.length ? parse(keys[keys.length - 1]) : addDays(today, 365);
    var view = new Date(today.getFullYear(), today.getMonth(), 1);
    var firstFree = keys.filter(function (k) { return parse(k) >= today && !busy[k]; })[0];
    if (firstFree) { var ff = parse(firstFree); view = new Date(ff.getFullYear(), ff.getMonth(), 1); }
    var minView = new Date(today.getFullYear(), today.getMonth(), 1);
    var maxView = new Date(lastPriced.getFullYear(), lastPriced.getMonth(), 1);
    var cin = null, cout = null, hover = null, guests = Math.min(data.baseGuests || 6, data.maxGuests || 13), msg = "";

    function nightOK(k) { return days[k] && !busy[k] && parse(k) >= today; }
    function check(a, b) {
      var n = Math.round((b - a) / 864e5), mn = (days[iso(a)] || {}).m || 1;
      for (var d = new Date(a); d < b; d = addDays(d, 1)) {
        var k = iso(d);
        if (busy[k]) return t.errBusy;
        if (!days[k]) return t.errNoPrice;
      }
      if (n < mn) return t.errMin(mn);
      return "";
    }

    function click(k) {
      var d = parse(k);
      if (!cin || cout || d <= cin) {
        if (!nightOK(k)) return;
        cin = d; cout = null; msg = "";
      } else {
        var e = check(cin, d);
        if (e) { msg = e; } else { cout = d; msg = ""; }
      }
      draw();
    }

    function month(m0) {
      var y = m0.getFullYear(), m = m0.getMonth();
      var h = "<div class='lrp-month'><h4>" + t.months[m] + " " + y + "</h4><div class='lrp-grid'>";
      t.days.forEach(function (d) { h += "<div class='lrp-dow'>" + d + "</div>"; });
      var first = (new Date(y, m, 1).getDay() + 6) % 7;
      for (var i = 0; i < first; i++) h += "<div class='lrp-d empty'></div>";
      var dim = new Date(y, m + 1, 0).getDate();
      var end = cout || (cin && hover && hover > cin ? hover : null);
      for (var dd = 1; dd <= dim; dd++) {
        var d = new Date(y, m, dd), k = iso(d), info = days[k], cls = "lrp-d";
        var past = d < today;
        if (past || !info) cls += " off";
        else if (busy[k]) cls += " busy";
        // a booked night can still be a check-out day
        if (cin && !cout && d > cin && (busy[k] || !info) && !check(cin, d)) cls = cls.replace(" busy", "").replace(" off", "") + " co";
        if (cin && +d === +cin) cls += " edge";
        else if (cout && +d === +cout) cls += " edge";
        else if (cin && end && d > cin && d < end) cls += " range";
        h += "<button type='button' class='" + cls + "' data-k='" + k + "'><span class='n'>" + dd + "</span></button>";
      }
      return h + "</div></div>";
    }

    function side() {
      var h = "", gopt = "";
      for (var g = 1; g <= (data.maxGuests || 13); g++) gopt += "<option" + (g === guests ? " selected" : "") + ">" + g + "</option>";
      h += "<div class='lrp-row'><span>" + t.guests + "</span><select class='lrp-g'>" + gopt + "</select></div>";
      if (!cin) {
        h += "<p class='lrp-hint'>" + t.pickIn + "</p>";
      } else {
        h += "<div class='lrp-row'><span>" + t.checkin + "</span><b>" + cin.toLocaleDateString(lang === "it" ? "it-IT" : "en-GB") + "</b></div>";
        var mn = (days[iso(cin)] || {}).m || 1;
        if (!cout) {
          h += "<p class='lrp-hint'>" + t.pickOut + "<br><small>" + t.minStay(mn) + "</small></p>";
        } else {
          var n = Math.round((cout - cin) / 864e5), sum = 0;
          for (var d = new Date(cin); d < cout; d = addDays(d, 1)) sum += days[iso(d)].p;
          var xg = Math.max(0, guests - (data.baseGuests || 6)), xf = xg * (data.extraGuestFee || 0) * n;
          var tot = sum + xf;
          h += "<div class='lrp-row'><span>" + t.checkout + "</span><b>" + cout.toLocaleDateString(lang === "it" ? "it-IT" : "en-GB") + "</b></div>";
          h += "<div class='lrp-row'><span>" + t.accommodation + " (" + t.nights(n) + ")</span><span>" + money(sum) + "</span></div>";
          if (xf) h += "<div class='lrp-row'><span>" + t.extra(xg, money(data.extraGuestFee)) + "</span><span>" + money(xf) + "</span></div>";
          h += "<div class='lrp-row lrp-tot'><b>" + t.total + "</b><b>" + money(tot) + "</b></div>";
          var body = t.body({ prop: data.property, inD: iso(cin), outD: iso(cout), n: n, g: guests, tot: money(tot) });
          var href = "mailto:" + data.email + "?subject=" + encodeURIComponent(t.subject + " " + iso(cin) + " - " + iso(cout)) + "&body=" + encodeURIComponent(body);
          h += "<a class='lrp-btn' target='_top' href='" + href + "'>" + t.request + "</a>";
        }
        h += "<button type='button' class='lrp-link lrp-clear'>" + t.clear + "</button>";
      }
      h += "<div class='lrp-msg'>" + msg + "</div>";
      if (data.notes && data.notes[lang]) h += "<div class='lrp-note'>" + data.notes[lang] + "</div>";
      if (data.generated) h += "<div class='lrp-upd'>" + t.updated + " " + new Date(data.generated).toLocaleDateString(lang === "it" ? "it-IT" : "en-GB") + "</div>";
      return h;
    }

    function draw() {
      var next = new Date(view.getFullYear(), view.getMonth() + 1, 1);
      var h = "<h3>" + t.title + "</h3>";
      h += "<p class='lrp-sub'>" + t.intro + "</p>";
      h += "<div class='lrp-wrap'><div class='lrp-cal'><div class='lrp-nav'><button type='button' class='lrp-prev'" + (view <= minView ? " disabled" : "") + ">‹</button><span></span><button type='button' class='lrp-next'" + (next > maxView ? " disabled" : "") + ">›</button></div>";
      h += "<div class='lrp-months'>" + month(view) + month(next) + "</div>";
      h += "<div class='lrp-legend'><span><i style='background:#f4f8f4;border:1px solid #cfe3d3'></i>" + t.legendFree + "</span><span><i style='background:#f2f2f2'></i>" + t.legendBusy + "</span><span><i style='background:#cfe3d3'></i>" + t.legendSel + "</span></div></div>";
      h += "<div class='lrp-side'>" + side() + "</div></div>";
      el.innerHTML = h;
      el.querySelector(".lrp-prev").onclick = function () { view = new Date(view.getFullYear(), view.getMonth() - 1, 1); draw(); };
      el.querySelector(".lrp-next").onclick = function () { view = next; draw(); };
      Array.prototype.forEach.call(el.querySelectorAll(".lrp-d[data-k]"), function (b) {
        b.onclick = function () { click(b.getAttribute("data-k")); };
        b.onmouseenter = function () { if (cin && !cout) { hover = parse(b.getAttribute("data-k")); paintRange(); } };
      });
      el.querySelector(".lrp-g").onchange = function (e) { guests = +e.target.value; draw(); };
      var c = el.querySelector(".lrp-clear"); if (c) c.onclick = function () { cin = cout = hover = null; msg = ""; draw(); };
    }

    function paintRange() {
      Array.prototype.forEach.call(el.querySelectorAll(".lrp-d[data-k]"), function (b) {
        var d = parse(b.getAttribute("data-k"));
        b.classList.toggle("range", !!(cin && hover && d > cin && d < hover));
      });
    }

    draw();
  }

  function boot() {
    var els = document.querySelectorAll("#lrp-calendar, .lrp-calendar");
    Array.prototype.forEach.call(els, init);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot();
})();
