/* store.js —— 用户改动的本地持久化（IndexedDB）
 * 只存「增量 delta」，基础数据(data.json / data_buildings.json)保持只读，便于重置。
 * delta = { added:[记录...], updated:{id:记录}, deleted:[id...] }
 *
 * v2.5.0 双数据层（需求二/三）：感知设备层用键 "delta"，水工建筑物层用独立键 "delta_bld"。
 * 采用「两个独立的 IndexedDB 键」而不是在同一对象里加子键（如 {dev:...,bld:...}），原因：
 *   ① 老用户已存在的设备增量（added/updated/deleted）零迁移、零丢数据风险——设备线的
 *      读写代码路径与历史上完全一致，一行未变；
 *   ② 建筑物层的写操作在物理上不可能碰到设备层：导入水工建筑物永远只 patch delta_bld，
 *      用户担心的「导入建筑物覆盖掉感知设备」在存储层就被结构性杜绝（不只是逻辑上判断）。
 */
(function (global) {
  const DB = "shuili_app";
  const STORE = "kv";
  const KEY = "delta";          // 感知设备层
  const KEY_BLD = "delta_bld";  // 水工建筑物层（v2.5.0）

  const EMPTY = () => ({ added: [], updated: {}, deleted: [] });
  let _db = null;

  function open() {
    if (_db) return Promise.resolve(_db);
    return new Promise((res, rej) => {
      const req = indexedDB.open(DB, 1);
      req.onupgradeneeded = () => req.result.createObjectStore(STORE);
      req.onsuccess = () => { _db = req.result; res(_db); };
      req.onerror = () => rej(req.error);
    });
  }

  function tx(mode) {
    return open().then((db) => db.transaction(STORE, mode).objectStore(STORE));
  }

  function getK(k) {
    return tx("readonly").then((os) => new Promise((res, rej) => {
      const r = os.get(k);
      r.onsuccess = () => res(r.result || EMPTY());
      r.onerror = () => rej(r.error);
    }));
  }

  function setK(k, delta) {
    return tx("readwrite").then((os) => new Promise((res, rej) => {
      const r = os.put(delta, k);
      r.onsuccess = () => res(delta);
      r.onerror = () => rej(r.error);
    }));
  }

  function norm(d) {
    d.added = d.added || [];
    d.updated = d.updated || {};
    d.deleted = d.deleted || [];
    return d;
  }

  async function patchK(k, fn) {
    const d = await getK(k);
    fn(d);
    norm(d);
    return setK(k, d);
  }

  function clearK(k) { return setK(k, EMPTY()); }

  async function exportK(k) { return JSON.stringify(await getK(k), null, 0); }

  async function importK(k, text) {
    const d = JSON.parse(text);
    if (!d || !Array.isArray(d.added)) throw new Error("格式不正确");
    return setK(k, norm({ added: d.added || [], updated: d.updated || {}, deleted: d.deleted || [] }));
  }

  // ---------- 感知设备层（历史 API，签名与行为完全不变）----------
  const Store = {
    layerKey: KEY,
    get: () => getK(KEY),
    set: (d) => setK(KEY, d),
    patch: (fn) => patchK(KEY, fn),
    clear: () => clearK(KEY),
    exportJSON: () => exportK(KEY),
    importJSON: (text) => importK(KEY, text),
    // ---------- 水工建筑物层（v2.5.0 新增；与设备层同一个 DB/对象仓，键不同）----------
    bld: {
      layerKey: KEY_BLD,
      get: () => getK(KEY_BLD),
      set: (d) => setK(KEY_BLD, d),
      patch: (fn) => patchK(KEY_BLD, fn),
      clear: () => clearK(KEY_BLD),
      exportJSON: () => exportK(KEY_BLD),
      importJSON: (text) => importK(KEY_BLD, text)
    }
  };

  // ---------- UI 偏好（轻量，存 localStorage；失败则静默降级）----------
  const UI_KEY = "ui_state";
  const ui = {
    get() { try { return JSON.parse(localStorage.getItem(UI_KEY)); } catch (e) { return null; } },
    set(s) { try { localStorage.setItem(UI_KEY, JSON.stringify(s)); } catch (e) {} },
    clear() { try { localStorage.removeItem(UI_KEY); } catch (e) {} }
  };

  global.Store = Store;
  Store.ui = ui;

  // ---------- 运行维护 / 旅游打卡 / 智能分析 业务数据（轻量，localStorage）----------
  const OPS_KEY = "ops_state";
  const ops = {
    get() { try { return JSON.parse(localStorage.getItem(OPS_KEY)) || {}; } catch (e) { return {}; } },
    set(s) { try { localStorage.setItem(OPS_KEY, JSON.stringify(s)); } catch (e) {} },
    clear() { try { localStorage.removeItem(OPS_KEY); } catch (e) {} }
  };
  Store.ops = ops;
})(window);
