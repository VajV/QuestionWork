(function () {
  if (typeof window === "undefined") return;

  var isLocalhost =
    window.location.hostname === "localhost" ||
    window.location.hostname === "127.0.0.1";
  if (!isLocalhost) return;

  var flag = "qwork-sw-reset-done";

  Promise.resolve()
    .then(function () {
      if (!("serviceWorker" in navigator)) return false;
      return navigator.serviceWorker.getRegistrations().then(function (registrations) {
        if (!registrations.length) return false;
        return Promise.all(
          registrations.map(function (registration) {
            return registration.unregister();
          }),
        ).then(function () {
          return true;
        });
      });
    })
    .then(function (hadRegistrations) {
      if (!("caches" in window)) return hadRegistrations;
      return caches.keys().then(function (keys) {
        var targetKeys = keys.filter(function (key) {
          return key.indexOf("qwork") === 0;
        });

        if (!targetKeys.length) return hadRegistrations;

        return Promise.all(
          targetKeys.map(function (key) {
            return caches.delete(key);
          }),
        ).then(function () {
          return true;
        });
      });
    })
    .then(function (didReset) {
      try {
        if (didReset && window.sessionStorage.getItem(flag) !== "1") {
          window.sessionStorage.setItem(flag, "1");
          window.location.reload();
          return;
        }

        window.sessionStorage.removeItem(flag);
      } catch (_) {}
    })
    .catch(function () {});
})();