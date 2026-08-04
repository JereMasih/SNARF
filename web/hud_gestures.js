/* ============================================================================
   HUD GESTURE CONTROLLER — capa de traducción de gestos → eventos abstractos
   (Fase 2 del plan de HUD, ver SESSION_STATE.md).

   Completamente desacoplada del render: no toca el DOM más allá de leer
   `data-hud-id` en los elementos que se le pasan, y solo emite callbacks
   semánticos (focus/blur/select/deselect). Hoy la única fuente de gestos es
   mouse/touch (`bindPointerSource`), pero cualquier fuente futura (ej. un
   puente de eye-tracking/visionOS, Fase 9) puede llamar directo a
   `.focus(id)`/`.blur(id)`/`.select(id)`/`.deselect()` sin que el componente
   de render se entere de qué generó el evento — ese es el punto entero de
   esta capa (pedido explícito del fundador).

   Estados abstractos, uno por nodo:
     - "collapsed" (default) — solo ícono.
     - "focus" — hover: se expande, no persiste al salir el mouse.
     - "select" — click: queda anclado hasta un deselect explícito (otro
       click sobre el mismo nodo, o `.deselect()`).
   Invariante: como mucho un nodo seleccionado a la vez (seleccionar uno
   nuevo deselecciona el anterior) — mismo criterio que cualquier HUD real,
   nunca dos paneles anclados compitiendo por espacio.
   ============================================================================ */

(function (global) {
  "use strict";

  function HUDGestureController(callbacks) {
    this._callbacks = callbacks || {};
    this._focused = null;
    this._selected = null;
  }

  HUDGestureController.prototype._emit = function (name, id) {
    var fn = this._callbacks[name];
    if (typeof fn === "function") fn(id);
  };

  // --- API pública, agnóstica de la fuente del gesto ---

  HUDGestureController.prototype.focus = function (id) {
    if (this._focused === id) return;
    if (this._focused !== null) this.blur(this._focused);
    this._focused = id;
    this._emit("onFocus", id);
  };

  HUDGestureController.prototype.blur = function (id) {
    if (this._focused !== id) return;
    this._focused = null;
    this._emit("onBlur", id);
  };

  HUDGestureController.prototype.select = function (id) {
    if (this._selected === id) {
      this.deselect();
      return;
    }
    var previous = this._selected;
    this._selected = id;
    if (previous !== null) this._emit("onDeselect", previous);
    this._emit("onSelect", id);
  };

  HUDGestureController.prototype.deselect = function () {
    if (this._selected === null) return;
    var id = this._selected;
    this._selected = null;
    this._emit("onDeselect", id);
  };

  HUDGestureController.prototype.state = function (id) {
    if (this._selected === id) return "select";
    if (this._focused === id) return "focus";
    return "collapsed";
  };

  // --- Fuente de gestos: mouse/touch sobre un contenedor real ---
  // Único punto que toca el DOM. Traduce mouseenter/mouseleave/click en
  // widgets con `data-hud-id` a las llamadas abstractas de arriba. Reemplazar
  // esto por un `bindGazeSource` futuro no requiere tocar el render.
  HUDGestureController.prototype.bindPointerSource = function (container) {
    var self = this;

    container.addEventListener("mouseenter", function (evt) {
      var el = evt.target.closest("[data-hud-id]");
      if (el) self.focus(el.getAttribute("data-hud-id"));
    }, true);

    container.addEventListener("mouseleave", function (evt) {
      var el = evt.target.closest("[data-hud-id]");
      if (el) self.blur(el.getAttribute("data-hud-id"));
    }, true);

    container.addEventListener("click", function (evt) {
      var el = evt.target.closest("[data-hud-id]");
      if (el) {
        self.select(el.getAttribute("data-hud-id"));
        return;
      }
      // Click fuera de cualquier widget (backdrop del panel anclado) cierra
      // la selección — "hasta que lo cierre yo" incluye clickear afuera.
      if (evt.target.closest("[data-hud-deselect]")) self.deselect();
    });
  };

  global.HUDGestureController = HUDGestureController;
})(typeof window !== "undefined" ? window : this);
