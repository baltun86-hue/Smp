package ru.smpspravochnik.app;

import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.view.WindowManager;
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

        // правка 2026-10 (8.12): внешние ссылки (https, mailto, tel) — только в системных приложениях
        // (браузер, почта, звонилка), никогда внутри справочника
        @JavascriptInterface
        public void openExternal(String url) {
            runOnUiThread(() -> {
                try {
                    Intent i = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
                    i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                    startActivity(i);
                } catch (Exception e) {
                    // нет подходящего приложения — молча игнорируем
                }
            });
        }

        // правка 2026-10 (8.26): пока идёт таймер СЛР — экран не гаснет (Wake Lock API в WebView нет;
        // при погасшем экране WebView засыпает и метроном замолкает)
        @JavascriptInterface
        public void keepScreenOn(boolean on) {
            runOnUiThread(() -> {
                if (on) getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
                else getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
            });
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
