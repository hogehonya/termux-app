# Android互換性と導入経路の設計見直し

更新日: 2026-11-04 JST。状態: **調査に基づく設計案。コード・SDK設定は未変更、実機での成立は未検証**。

## 要求と対象

要求者はhogehonya。出所は本会話の「日本語化とフォントJP化をまずイシューで」「android対応を7plusで」「一番右に1列追加しよう」、および追加指示「設計と方針を調べてリポジトリに反映させろ」「設計を見直せ」。要求の正本はGitHubの既存Issueとする。

| 要求 | 追跡先 | 今回の設計で維持すること |
| --- | --- | --- |
| 日本語化 | [#1](https://github.com/hogehonya/termux-app/issues/1)、[PR #5](https://github.com/hogehonya/termux-app/pull/5) | 実装済み163項目と検証を保全する。実機未確認を完了にしない |
| 中文向け字形の残存解消 | [#2](https://github.com/hogehonya/termux-app/issues/2) | UI・ターミナルのフォールバックと桁幅を検証する。フォント名は未指定 |
| Android 7.0以上 | [#3](https://github.com/hogehonya/termux-app/issues/3) | 最低対応API24。targetSdkとは別に管理し、Android 11以上へ勝手に狭めない |
| 右端のセッション切替列 | [#4](https://github.com/hogehonya/termux-app/issues/4) | 画面右端に縦1列。ラベル・幅などの未採用案を確定仕様にしない |

今回の追加課題は、Pixel 7でAPKを導入し、bootstrap・シェル・パッケージが動く状態へ到達する方法の設計。Google Playでの配布や他アプリの統合は要求に追加しない。

## 確認済みの現状

- 既定ブランチは`master`、調査基準は`8629e632fcb95da272221be327db653fb24befe9`。日本語化PR #5のheadは`65e40b838eb98d3a0cd4585e519fb34412e24e1f`。最終APKのbuild・署名、日本語検証12件、既存単体147件、同headのCI 4checksと独立レビューは成功済み。実機動作とマージは未完了。
- `gradle.properties`はminSdk21、targetSdk28、compileSdk36。既定bootstrapは`apt-android-7`。Issue #3の最低API24化は未実装。
- .20本体でPixel 7/API37の認証済みUSB接続を確認。サンドボックス内のADB一覧が空でも、本体に接続がないとは判定できない。端末serialは公開記録に含めない。
- 最終APKのSHA256は`ea2ab421287f2d427b59914b566b5b05d56090843b027e15c5d428d60d94b55d`。このAPKの導入を1回試行し、`INSTALL_FAILED_VERIFICATION_FAILURE`で拒否された。画面にはPlayプロテクトの「Androidの以前のバージョンを対象」との説明が出た。
- これは少なくとも今回観測した**検証機能による導入拒否**である。`INSTALL_FAILED_DEPRECATED_SDK_VERSION`などのOS側の最低target制限と同一視しない。targetを上げれば必ず警告が消える、とも断定しない。
- 保存済みarm64 bootstrap（`2026.02.12-r1+apt.android-7`）の`var/lib/dpkg/status`には公式`termux-exec 1:2.4.0-1`が入っている。direct/linker両方のpreloadライブラリと`bin/login`のpreload設定を実ファイルから確認した。**現bootstrapを捨ててPlay版へ移ることが必須、とはいえない**。

既存lintエラー4件は[#6](https://github.com/hogehonya/termux-app/issues/6)で別追跡する。既存のCI成功をlint成功や実機確認へ読み替えない。

## 比較と結論

| 選択肢 | 得られること | 制約・判断 |
| --- | --- | --- |
| target28の現APKを維持 | 既存のパッケージ・動作を維持 | 今回の端末では導入拒否が未解消。公式Discussionには個別許可で導入した報告があるが、本端末での許可成立は未確認。保護機能を無効化する手順を製品設計の前提にしない |
| targetの数字だけ変更 | APKの宣言が新しくなる | Android 10以降のアプリデータ実行制限、通知・サービス等の対応を欠く。導入成功だけでシェル動作を保証しないため不採用案 |
| 古い`android-10`ブランチを統合 | target30/min24の試作が存在 | 先端commitは2021-02-12の`e783f406`。APK型パッケージ管理への変更を含む別方式であり、現在のapt環境へそのまま統合する案は採らない |
| 現行Play版へ全面移行 | 現在のtargetを使う実装例がある | 調査時head `fea9fe2cfc484c621e5bf7e42875dab3277b8f90`はmin30/target37。別bootstrap、パッケージ修正、プラグイン構成変更を伴う。Android 7要求を失うので全面移行は推奨しない |
| 現フォーク＋公式の現行実行対応を必要箇所へ適用 | apt環境と日本語化を保持し、min24と新targetの両立を検証できる | **推奨する実証候補**。初回シェル起動、子プロセス、サービス・権限、パッケージ互換性を一緒に確認する。成立済みではない |

設計者の推奨は最後の案。Android 7用と現行Android用のAPK二系統化も、現時点では必須としない。ユーザーが承認した実装方式・targetの具体値という意味ではない。

## 実証する構成

### SDKとバージョン境界

最低対応はAPI24を維持する。targetの実証候補には現行Play版と同じAPI37を置くが、これは**未採用の比較基準**であり、現在のcompileSdk36でそのまま変更できるとは扱わない。必要なSDKと依存APIを確認し、採用targetを実証結果とともに記録する。値だけを上げたAPKを完成品として配布しない。

1つのコードベース内でOSバージョンに応じた処理を分ける。API24側にないAPIは適切にガードし、古い端末を新しいAPIの呼び出しでクラッシュさせない。最低対応とtarget、compileSdk、実測した端末APIを混同しない。

### シェルとパッケージ

Androidの公式仕様では、target29以上のアプリはアプリホーム内の実行ファイルを直接`execve()`できない。現行公式`termux-exec`にはsystem linkerを使う実行対応があり、同梱2.4.0もその系統にある。ただし**Java/JNIから最初に起動するプロセス**と、起動後にpreloadが処理する子プロセスは別である。

- 初回の起動引数を組み立てる`termux-shared/.../shell/TermuxShellUtils.java`、実際に起動する`terminal-emulator`と共通のshell runnerを確認する。ターミナルとバックグラウンド実行で片方だけ対応する設計を避ける。
- 参照実装は現行Play版の`TermuxShellUtils.java`。取り込み候補は起動方式の必要箇所だけとし、UI・パッケージ管理の全面置換はしない。
- 現フォークの`TermuxAppShellEnvironment`は既にアプリのtargetSdk等を環境へ渡す。実装時はその経路と、同梱`login`・`libtermux-exec-ld-preload.so`の選択が整合するかを確認する。古いPlay版の`libtermux-exec.so`名を無条件にコピーしない。
- 既定の`apt-android-7`と公式パッケージ源は、実証で問題が確認されるまで維持する。Play用bootstrapを従来のprefixへ混在させない。
- preloadを経由しない直接syscall、静的バイナリ、`/proc/self/exe`へ依存するプログラム等の制約がある。一般的なシェル操作が通ったことを「全パッケージ対応」としない。必要な修正がアプリ外パッケージに及ぶ場合は、その範囲と採用判断を示す。

これはupstreamで使われるアプリ実行方式の互換設計であり、端末の検証設定・SELinux・Playプロテクトを変更する設計ではない。

### 通知・サービス・ストレージ

target更新は実行方式だけの変更ではない。今回のソースでも`TermuxService`の通知用`PendingIntent`はflagsが0、manifestには旧ストレージ互換設定がある。新targetで以下の経路を点検し、必要な対応に限定して実証する。

- 通知の権限要求・拒否時の動作と、通知アクションの`PendingIntent`可変性。
- フォアグラウンドサービスの種別・権限・起動条件と、アプリを離れて戻った時のセッション継続。
- ユーザーが選ぶ共有ファイルへのアクセス。既存ホーム内のパッケージ利用と、共有ストレージへのアクセスを分けて検証する。
- 初回bootstrapの展開、起動、更新、既存データへの影響。失敗をデータ削除や保護機能無効化で回避しない。

プラグインの統合、sharedUserIdの撤去、権限の一括追加、署名・applicationIdの変更はここから自動採用しない。必要性が判明した項目だけ、互換性と配布条件を示して設計へ戻す。

## 検証と進行条件

| 環境・経路 | 観測する結果 | 現在の結果 |
| --- | --- | --- |
| API24環境 | インストール、初回bootstrap、シェル・子プロセス、日本語UI、通知と再開 | 未検証。実機・エミュレータの別も記録する |
| API29境界の環境 | 新targetでの実行方式と従来側との分岐 | 未検証 |
| .20接続のPixel 7/API37 | 保護設定を変えず導入できるか、警告の有無、導入実体のhashとSDK | target28の最終APKは拒否。新targetは未実装 |
| 新targetでの初回・再起動 | bootstrap展開、login、対話シェル、失敗時の説明 | 未検証 |
| 子プロセス・パッケージ | `sh`/`bash`、パイプ、shebang付きスクリプト、`pkg`更新・追加と実行 | 未検証 |
| SSH・セッション | テスト先へのSSH、複数セッション、バックグラウンド・復帰 | 未検証。実行中の別作業を停止しない |
| 日本語・後続要件 | #1の日本語表示、#2の字形と桁幅、#4の切替列 | #1は自動検証のみ成功。#2/#4は未着手 |

実装時は、まず保存済み日本語化を失わない隔離ブランチでSDK・起動方式の実証を行う。build、既存単体、日本語検証、独立レビュー、CIだけでなく、導入とシェル・`pkg`・SSHの確認が成立してから、製品へ取り込む可否を判断する。API24はエミュレータだけならその旨を明記し、実機確認と同一扱いしない。

進捗は#1/#3へ紐づける。互換性対応は#1の実機確認を妨げている前提課題として扱い、#1を未検証のまま閉じて#2/#4へ進まない。target対応を次の実装対象へ変更する必要があることと、今回の設計文書反映は区別する。現在のPR #5はdraftのまま保全する。

### 判定

- **実証に進める根拠あり**: 公式の現行対応が存在し、bootstrapにも既に対応ライブラリが入っている。
- **採用・完了は未判定**: 本フォークの新targetでの導入、全起動経路、API24、必要なパッケージ互換性をまだ測定していない。
- **次の操作**: 本設計と#3の未決事項を確認し、SDK・初回起動経路の実証範囲を固定する。現APKを反復導入したり、数字だけを変更して配布したりしない。

## 根拠と参照

調査日は2026-11-04。ソース値は下記commitまたは同梱bootstrapの実測値で固定する。古いWikiの「Play版は更新されない」という説明は、現行Play版の状態より優先しない。

1. [Android 10: アプリホームからの直接実行制限](https://developer.android.com/about/versions/10/behavior-changes-10#execute-permission)
2. [Android 15: 最低targetによる導入拒否とエラーの区別](https://developer.android.com/about/versions/15/behavior-changes-all#minimum-target-api-level) — API37の閾値をこのページから推定しない。
3. [公式termux-execの技術文書](https://github.com/termux/termux-exec-package/blob/2cd0ba6b907565484130851f9617523c98df8615/site/pages/en/projects/docs/technical/index.md)、[2.0.0での実行対応](https://github.com/termux/termux-exec-package/blob/2cd0ba6b907565484130851f9617523c98df8615/site/pages/en/projects/releases/2/v2.0.0.md)
4. [現行Play版のSDK設定](https://github.com/termux-play-store/termux-apps/blob/fea9fe2cfc484c621e5bf7e42875dab3277b8f90/gradle.properties)、[初回起動の参照実装](https://github.com/termux-play-store/termux-apps/blob/fea9fe2cfc484c621e5bf7e42875dab3277b8f90/termux-app/src/main/java/com/termux/app/TermuxShellUtils.java)、[Play版の構成・対応OS](https://github.com/termux-play-store)
5. [旧android-10の先端](https://github.com/termux/termux-app/commit/e783f406) — 2021年の別方式。現行対応の証拠にはしない。
6. [公式リポジトリの同種Discussion](https://github.com/termux/termux-app/discussions/4693) — 個別の導入報告であり、本端末での成立や全端末共通の仕様ではない。
7. [Playプロテクトの開発者向け案内](https://support.google.com/googleplay/answer/2812853?hl=en) — 誤検出の申立て経路はあるが、今回の申立て・APK送信は未実施。
