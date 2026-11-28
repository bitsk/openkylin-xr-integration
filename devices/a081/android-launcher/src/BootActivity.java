package com.bits.qiyu.boot;

import android.app.Activity;
import android.os.Bundle;
import android.util.Log;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.util.concurrent.TimeUnit;

public final class BootActivity extends Activity {
    private String target;
    private String title;
    private TextView status;
    private Button reboot;
    private boolean confirming;
    private boolean ready;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        target = getPackageName().substring(getPackageName().lastIndexOf('.') + 1);
        if (target.equals("openkylin")) title = "openKylin";
        else if (target.equals("steamos")) title = "SteamOS";
        else if (target.equals("debian")) title = "Debian";
        else { finish(); return; }
        // Qiyu Home presents ordinary Android activities in its interactive VR
        // window and maps the controller ray to Android touch events.
        setContentView(makePane());
        getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LAYOUT_STABLE
            | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
            | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_FULLSCREEN
            | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY);
        run("preflight");
    }

    private LinearLayout makePane() {
        LinearLayout pane = new LinearLayout(this);
        pane.setOrientation(LinearLayout.VERTICAL);
        pane.setGravity(Gravity.CENTER);
        pane.setPadding(48, 32, 48, 32);
        pane.setBackgroundColor(0xff101b2c);
        TextView heading = new TextView(this);
        heading.setText("进入 " + title);
        heading.setTextColor(0xffeef5ff);
        heading.setTextSize(28);
        heading.setGravity(Gravity.CENTER);
        pane.addView(heading);
        TextView explanation = new TextView(this);
        explanation.setText(target.equals("openkylin")
            ? "请先安装 openKylin Alpha。确认后将重启到当前槽位的 recovery。"
            : "重启后本次进入 " + title + "。\n默认启动系统保持原设置。");
        explanation.setTextColor(0xffcedaeb);
        explanation.setTextSize(18);
        explanation.setGravity(Gravity.CENTER);
        explanation.setPadding(0, 20, 0, 20);
        pane.addView(explanation);
        status = new TextView(this);
        status.setGravity(Gravity.CENTER);
        status.setTextColor(0xffcedaeb);
        status.setTextSize(18);
        pane.addView(status);
        reboot = new Button(this);
        reboot.setAllCaps(false);
        reboot.setText("重启进入 " + title);
        reboot.setTextSize(22);
        reboot.setEnabled(false);
        pane.addView(reboot);
        reboot.setOnClickListener(v -> {
            if (!ready) return;
            if (!confirming) {
                confirming = true;
                status.setText("确认重启？当前 Android 应用将关闭。");
                reboot.setText("确认重启进入 " + title);
            } else run("reboot");
        });
        Button close = new Button(this);
        close.setAllCaps(false);
        close.setText("返回 Android");
        close.setOnClickListener(v -> finish());
        pane.addView(close);
        return pane;
    }

    private void run(String action) {
        ready = false;
        reboot.setEnabled(false);
        boolean alpha = target.equals("openkylin");
        boolean checking = action.equals("preflight");
        status.setText(checking
            ? (alpha ? "正在请求 root 授权…" : "正在检查安装…") : "正在准备重启…");
        new Thread(() -> {
            String output;
            boolean ok = false;
            try {
                ProcessBuilder request;
                if (alpha) {
                    request = new ProcessBuilder("su", "-c",
                        checking ? "id -u" : "/system/bin/reboot recovery");
                } else {
                    request = new ProcessBuilder("su", "-mm", "-c",
                        "sh /data/adb/qiyu-boot/control.sh " + action + " " + target);
                }
                Process process = request.redirectErrorStream(true).start();
                if (!process.waitFor(45, TimeUnit.SECONDS)) {
                    process.destroyForcibly();
                    throw new Exception("root 请求超时，请检查授权后重新打开");
                }
                ByteArrayOutputStream buffer = new ByteArrayOutputStream();
                try (InputStream stream = process.getInputStream()) {
                    byte[] block = new byte[1024];
                    int count;
                    while ((count = stream.read(block)) != -1) buffer.write(block, 0, count);
                }
                output = buffer.toString("UTF-8").trim();
                ok = checking && process.exitValue() == 0
                    && (alpha ? output.equals("0") : output.contains("READY " + target));
                Log.i("QiyuBoot", action + " " + target + " exit=" + process.exitValue() + " " + output);
                if (ok) {
                    int notice = output.indexOf("NOTICE ");
                    output = (alpha ? "已获 root 授权。" : "已就绪，可重启进入 " + title)
                        + (notice >= 0 ? "\n" + output.substring(notice + 7) : "");
                }
                else if (!checking && process.exitValue() == 0) output = "已请求重启。";
                else if (alpha && checking) output = "未获 root 授权。请在 Magisk 授权后重新打开。";
                else if (output.isEmpty()) output = "检查未通过，请确认 root 授权和系统安装";
            } catch (Exception error) {
                output = alpha && checking ? "无法取得 root 权限。请检查 Magisk 授权后重新打开。" : error.getMessage();
                Log.e("QiyuBoot", "Boot request failed", error);
            }
            final String text = output;
            final boolean enabled = ok;
            runOnUiThread(() -> {
                if (isFinishing() || isDestroyed()) return;
                ready = enabled;
                status.setText(text);
                reboot.setEnabled(enabled);
            });
        }, "boot-preflight").start();
    }
}
