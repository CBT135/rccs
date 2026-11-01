import Toybox.Communications;
import Toybox.Lang;
import Toybox.PersistedContent;
import Toybox.System;
import Toybox.Time;

// Dépôt public où la tâche GitHub publie la trace.
const RCCS_BASE_URL = "https://raw.githubusercontent.com/cbt135/rccs/main/trace/";

class RccsDownloader {

    private var _view as RccsView;
    private var _name as String? = null;
    private var _course = null;      // PersistedContent.Course une fois enregistré
    private var _busy as Boolean = false;

    function initialize(view as RccsView) {
        _view = view;
    }

    function isBusy() as Boolean {
        return _busy;
    }

    function hasCourse() as Boolean {
        return _course != null;
    }

    // 1. Lit le nom de la trace (trace/latest.txt, servi en text/plain par GitHub).
    function start() as Void {
        if (_busy) {
            return;
        }
        if (!(Toybox has :Communications) || !(Toybox has :PersistedContent)) {
            _view.show("Montre non compatible", "téléchargement de parcours");
            return;
        }
        _busy = true;
        _course = null;
        _view.show("Recherche", "de la trace...");
        Communications.makeWebRequest(
            RCCS_BASE_URL + "latest.txt",
            { "t" => Time.now().value() },          // évite le cache de GitHub
            {
                :method => Communications.HTTP_REQUEST_METHOD_GET,
                :responseType => Communications.HTTP_RESPONSE_CONTENT_TYPE_TEXT_PLAIN
            },
            method(:onName)
        );
    }

    function onName(code as Number, data) as Void {
        if (code != 200 || !(data instanceof String)) {
            fail(code);
            return;
        }
        var name = cleanName(data as String);
        if (name.length() == 0) {
            _busy = false;
            _view.show("Aucune trace", "sur GitHub");
            return;
        }
        _name = name;

        // Déjà sur la montre ? On ne le télécharge pas une seconde fois.
        var existing = findCourse(name);
        if (existing != null) {
            _course = existing;
            _busy = false;
            _view.showDone(name, "déjà sur la montre");
            return;
        }

        // 2. Télécharge le FIT : la montre l'enregistre d'elle-même dans les parcours.
        _view.show("Téléchargement", name);
        Communications.makeWebRequest(
            RCCS_BASE_URL + name + ".fit",
            { "t" => Time.now().value() },
            {
                :method => Communications.HTTP_REQUEST_METHOD_GET,
                :responseType => Communications.HTTP_RESPONSE_CONTENT_TYPE_FIT
            },
            method(:onFit)
        );
    }

    function onFit(code as Number, data) as Void {
        _busy = false;
        if (code != 200) {
            fail(code);
            return;
        }
        var course = null;
        if (data instanceof PersistedContent.Iterator) {
            course = (data as PersistedContent.Iterator).next();
        }
        if (course == null) {
            course = findCourse(_name as String);
        }
        _course = course;
        _view.showDone(_name as String, "enregistré dans Parcours");
    }

    // Lance la navigation sur le parcours (bouton START / appui écran).
    function startCourse() as Void {
        if (_course != null) {
            System.exitTo(_course.toIntent());
        }
    }

    private function findCourse(name as String) {
        var it = PersistedContent.getCourses();
        if (it == null) {
            return null;
        }
        var c = it.next();
        while (c != null) {
            var n = c.getName();
            if (n != null && n.equals(name)) {
                return c;
            }
            c = it.next();
        }
        return null;
    }

    // Garde uniquement chiffres, lettres et tirets (retire le retour à la ligne).
    private function cleanName(s as String) as String {
        var out = "";
        var chars = s.toCharArray();
        for (var i = 0; i < chars.size(); i++) {
            var ch = chars[i];
            if ((ch >= '0' && ch <= '9') || (ch >= 'A' && ch <= 'Z') || (ch >= 'a' && ch <= 'z') || ch == '-') {
                out += ch.toString();
            }
        }
        return out;
    }

    private function fail(code as Number) as Void {
        _busy = false;
        var msg;
        if (code == Communications.BLE_CONNECTION_UNAVAILABLE) {
            msg = "Téléphone non connecté";
        } else if (code == Communications.NETWORK_REQUEST_TIMED_OUT) {
            msg = "Délai dépassé";
        } else if (code == 404) {
            msg = "Trace introuvable";
        } else if (code == Communications.STORAGE_FULL) {
            msg = "Mémoire pleine";
        } else {
            msg = "Erreur " + code.toString();
        }
        _view.showError(msg);
    }
}
