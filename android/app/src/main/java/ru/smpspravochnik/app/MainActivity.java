package ru.smpspravochnik.app;

import android.os.Bundle;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;
import androidx.activity.OnBackPressedCallback;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {

    // правка 2026-10: мост для выхода — index.html вызывает AndroidExit.exitApp()
    // после второго «Назад» на главном экране (иначе нужно три нажатия)
    public class ExitBridge {
        @JavascriptInterface
        public void exitApp() {
            runOnUiThread(() -> finish());
        }
    }

    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        WebView wv = getBridge().getWebView();
        if (wv != null) wv.addJavascriptInterface(new ExitBridge(), "AndroidExit");

        // правка 2026-10: «Назад» (кнопка и жест) — не сворачивать приложение, а отдать
        // справочнику: шаг истории WebView → popstate → handleAndroidBack() в index.html
        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override
            public void handleOnBackPressed() {
                WebView w = getBridge() != null ? getBridge().getWebView() : null;
                if (w != null && w.canGoBack()) {
                    w.goBack();
                } else {
                    // истории нет (не должно случаться — справочник держит сторожевую запись)
                    setEnabled(false);
                    getOnBackPressedDispatcher().onBackPressed();
                    setEnabled(true);
                }
            }
        });
    }
}
