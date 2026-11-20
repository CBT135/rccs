import Toybox.Graphics;
import Toybox.Lang;
import Toybox.Time;
import Toybox.Time.Gregorian;
import Toybox.WatchUi;

class RccsView extends WatchUi.View {

    private var _title as String = "Trace RCCS";
    private var _line as String = "";
    private var _hint as String = "";
    private var _color as Number = Graphics.COLOR_WHITE;
    private var _started as Boolean = false;
    var downloader = null;   // renseigné par le délégué

    function initialize() {
        View.initialize();
    }

    function onShow() as Void {
        // Le téléchargement démarre dès l'ouverture de l'application.
        if (!_started && downloader != null) {
            _started = true;
            downloader.start();
        }
    }

    function show(title as String, line as String) as Void {
        set(title, line, "", Graphics.COLOR_WHITE);
    }

    // Le nom de la trace commence par sa date (AAAAMMJJ-RCCS) : on la compare à aujourd'hui.
    function showDone(name as String, line as String) as Void {
        var traceDay = dayOf(name);
        if (traceDay == null) {
            set(name, line, "START : suivre", Graphics.COLOR_GREEN);
            return;
        }
        var td = traceDay as Number;
        var info = Gregorian.info(Time.now(), Time.FORMAT_SHORT);
        var today = (info.year as Number) * 10000 + (info.month as Number) * 100 + (info.day as Number);
        if (td == today) {
            set(name, line, "START : suivre", Graphics.COLOR_GREEN);
        } else if (td < today) {
            // Ancienne trace : aucune trace n'a été publiée pour aujourd'hui.
            set("Trace du " + ddmm(td), "Pas de trace aujourd'hui", "START : suivre quand même", Graphics.COLOR_ORANGE);
        } else {
            set(name, "pour le " + ddmm(td), "START : suivre", Graphics.COLOR_GREEN);
        }
    }

    private function dayOf(name as String) as Number? {
        if (name.length() < 8) {
            return null;
        }
        var head = name.substring(0, 8);
        if (head == null) {
            return null;
        }
        var n = (head as String).toNumber();
        if (n == null || (n as Number) < 20000101) {
            return null;
        }
        return n as Number;
    }

    private function ddmm(yyyymmdd as Number) as String {
        var d = yyyymmdd % 100;
        var m = (yyyymmdd / 100) % 100;
        return d.format("%02d") + "/" + m.format("%02d");
    }

    function showError(msg as String) as Void {
        set("Échec", msg, "START : réessayer", Graphics.COLOR_RED);
    }

    private function set(title as String, line as String, hint as String, color as Number) as Void {
        _title = title;
        _line = line;
        _hint = hint;
        _color = color;
        WatchUi.requestUpdate();
    }

    function onUpdate(dc as Dc) as Void {
        dc.setColor(Graphics.COLOR_BLACK, Graphics.COLOR_BLACK);
        dc.clear();
        var cx = dc.getWidth() / 2;
        var h = dc.getHeight();
        dc.setColor(_color, Graphics.COLOR_TRANSPARENT);
        dc.drawText(cx, h * 0.36, Graphics.FONT_MEDIUM, _title, Graphics.TEXT_JUSTIFY_CENTER | Graphics.TEXT_JUSTIFY_VCENTER);
        dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_TRANSPARENT);
        dc.drawText(cx, h * 0.55, Graphics.FONT_SMALL, _line, Graphics.TEXT_JUSTIFY_CENTER | Graphics.TEXT_JUSTIFY_VCENTER);
        if (_hint.length() > 0) {
            dc.setColor(Graphics.COLOR_LT_GRAY, Graphics.COLOR_TRANSPARENT);
            dc.drawText(cx, h * 0.74, Graphics.FONT_XTINY, _hint, Graphics.TEXT_JUSTIFY_CENTER | Graphics.TEXT_JUSTIFY_VCENTER);
        }
    }
}
