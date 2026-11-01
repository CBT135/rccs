import Toybox.Graphics;
import Toybox.Lang;
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

    function showDone(name as String, line as String) as Void {
        set(name, line, "START : suivre", Graphics.COLOR_GREEN);
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
