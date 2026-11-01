import Toybox.Lang;
import Toybox.WatchUi;

class RccsDelegate extends WatchUi.BehaviorDelegate {

    private var _downloader as RccsDownloader;

    function initialize(downloader as RccsDownloader) {
        BehaviorDelegate.initialize();
        _downloader = downloader;
    }

    // START (ou appui sur l'écran) : suit le parcours s'il est prêt, sinon relance.
    function onSelect() as Boolean {
        if (_downloader.isBusy()) {
            return true;
        }
        if (_downloader.hasCourse()) {
            _downloader.startCourse();
        } else {
            _downloader.start();
        }
        return true;
    }
}
