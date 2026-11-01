import Toybox.Application;
import Toybox.Lang;
import Toybox.WatchUi;

// Application « Trace RCCS » : au lancement, télécharge depuis GitHub la dernière
// trace du club (fichier GPX nommé AAAAMMJJ-RCCS) et l'enregistre dans les
// parcours de la montre.
class RccsApp extends Application.AppBase {

    function initialize() {
        AppBase.initialize();
    }

    function onStart(state as Dictionary?) as Void {
    }

    function onStop(state as Dictionary?) as Void {
    }

    function getInitialView() {
        var view = new RccsView();
        var downloader = new RccsDownloader(view);
        view.downloader = downloader;
        return [view, new RccsDelegate(downloader)];
    }
}
