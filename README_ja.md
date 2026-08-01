<p align="center">
  <img src="docs/assets/banner.svg" alt="clutch" width="100%">
</p>

[English](README.md) · [Deutsch](README_de.md) · [Español](README_es.md) · [简体中文](README_zh-Hans.md) · [日本語](README_ja.md) · [Русский](README_ru.md)

# clutch

> 自動学習機能を搭載したプロバイダー非依存の LLM オーケストレーションエンジン

![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue)
![License MIT](https://img.shields.io/badge/License-MIT-green)
![Version 0.4.0](https://img.shields.io/badge/Version-0.4.0-orange)

**clutch**（ドイツ語：*Kupplung*、「クラッチ」）は、ドライビングのメタファーを用いて、複数のプロバイダーにまたがる最適な LLM モデルへタスクをインテリジェントにルーティングします。タスクの複雑さと目的を分析し、適切なモデルと推論レベルを選択し、予算を追跡し、経験から学習します。**ライブラリ**、**CLI**、または**ローカル Web アプリ**として使用できます。

## 機能

- **プロバイダー非依存** — Anthropic（Claude）、Google（Gemini）、Ollama（ローカル・リモート）、Claude Code、および **Kimi**（Moonshot API / CLI / Ollama Cloud）をサポート
- **自動ルーティング** — タスクの複雑さ*と目的*（コーディング、ビジョン、調査、バルク処理）を分析し、最適なモデル + 推論レベルを選択
- **目的・ビジョン対応** — 画像/ドキュメント入力をビジョン対応モデルにルーティング；タスクをモデルの強みに合わせて割り当て
- **CLI + Web UI** — `clutch route/run/chat/models/stats`、およびオプションの FastAPI Web チャット（`clutch serve --web`）
- **認証情報ストア** — API キーを `~/.clutch/credentials.json` に安全に保存（`clutch keys ...`）；環境変数が優先
- **モデル自動検出** — インストール済み Ollama モデル（ローカル/リモート）および OpenAI 互換 `/v1/models` エンドポイントを自動検出
- **予算追跡** — 4 段階の燃料計（緑/黄/橙/赤）で日次・月次の制限を管理
- **学習エンジン** — フィットネスのスコアリングと epsilon-greedy 探索によってルーティングを継続的に改善
- **実行パターン** — 単一タスク、チェーン（Kolonne/コンボイ）、並列チーム、スウォーム処理
- **ヘルスモニタリング** — サーキットブレーカー、レイテンシ追跡、オーバーキル/トークン爆発アラート、プロバイダーフェイルオーバー
- **SQLite メトリクス** — 永続的な走行ログ、チャットセッション、プロンプトライブラリ、プロファイル

## アーキテクチャ

システム全体が**自動車/ドライビングのメタファー**に従っています（コード識別子にはドイツ語用語を使用）：

```
                    +----------------------------------+
                    |            FAHRER                 |
                    |        (Driver / Orchestrator)    |
                    |     Any LLM: Opus, Gemini, ...   |
                    +--------+----------+--------------+
                             |          |
                +------------+          +-------------+
                |                                     |
        +-------v--------+                   +--------v-------+
        |    STRECKE      |                   |    GETRIEBE    |
        | (Road / Task    |                   | (Gearbox /     |
        |  Analysis)      |                   |  Model Registry|
        +----------------+                   |                |
                                              | G1: Haiku      |
        +----------------+                   | G2: Flash      |
        |   GAS / BREMSE  |                   | G3: Sonnet     |
        | (Throttle/Brake |                   | G4: Gemini Pro |
        |  Reasoning Lvl) |                   | G5: Opus       |
        +----------------+                   | + Ollama local |
                                              +----------------+
        +----------------+
        |    KUPPLUNG     |    +------------+    +-------------+
        | (Clutch / Model |    |   TACHO    |    |  TANKUHR    |
        |  Switching)     |    | (Metrics)  |    | (Budget)    |
        +----------------+    +------------+    +-------------+
```

| コンポーネント | 役割 | モジュール |
|-----------|------|--------|
| **Fahrer**（ドライバー） | オーケストレーター — モデル・推論・実行パターンを選択 | `fahrer.py` |
| **Strecke**（コース） | タスクの分析と分類 | `strecke.py` |
| **Getriebe**（ギアボックス） | プロバイダー非依存のモデルレジストリ | `getriebe.py` |
| **Gang**（ギア） | 特定のモデル（G1--G5） | `getriebe.py` |
| **Gas/Bremse**（アクセル/ブレーキ） | 推論レベル（0--100%） | `gas_bremse.py` |
| **Kupplung**（クラッチ） | モデル切り替えメカニズム | `kupplung.py` |
| **MotorBlock**（エンジンブロック） | 統一 API 呼び出し層 | `motorblock.py` |
| **Tacho**（スピードメーター） | メトリクス収集 | `tacho.py` |
| **Tankuhr**（燃料計） | 予算追跡（4 ゾーン） | `tankuhr.py` |
| **Bordcomputer**（車載コンピューター） | ヘルスモニター、サーキットブレーカー | `bordcomputer.py` |
| **Fahrtenbuch**（走行記録簿） | SQLite メトリクスストレージ | `fahrtenbuch.py` |
| **Fahrschule**（自動車学校） | 学習 / 進化エンジン | `fahrschule.py` |

## コースタイプ

| コース | 難易度 | デフォルトギア | アクセル | パターン |
|------|-----------|-------------|----------|---------|
| Feldweg（未舗装路） | 簡単 | Haiku (G1) | 30% | 単一 |
| Landstrasse（地方道） | 標準 | Sonnet (G3) | 50% | 単一 |
| Bundesstrasse（国道） | バグ修正 | Sonnet (G3) | 70% | 単一 |
| Autobahn（高速道路） | アーキテクチャ設計 | Opus (G5) | 90% | 単一 |
| Rallye（ラリー） | バルク処理 | Haiku (G1) | 30% | スウォーム |
| Konvoi（コンボイ） | パイプライン | Sonnet (G3) | 50% | チェーン |
| Teamfahrt（チーム走行） | マルチファイル | Sonnet (G3) | 50% | チーム |
| Langstrecke（長距離） | 複合タスク | Opus (G5) | 90% | ハイブリッド |

## インストール

```bash
git clone https://github.com/ellmos-ai/clutch.git
cd clutch
pip install -e .
```

### 要件

- Python 3.10+
- 使用するプロバイダーの API キー（環境変数として設定）：
  - Claude モデル用：`ANTHROPIC_API_KEY`
  - Gemini モデル用：`GOOGLE_API_KEY`
  - ローカルモデル用：Ollama をローカルで実行

## クイックスタート

```python
from clutch import Fahrer

# ドライバーを作成（設定済みの全プロバイダーを使用）
fahrer = Fahrer()

# タスクを記述 — ドライバーがすべてを処理
result = fahrer.fahren(
    "Fix the authentication bug in the login module",
    handler=my_handler,
)

# 選択された設定を確認
print(result.config.gang.name)       # "claude-sonnet"
print(result.config.gang.provider)   # "anthropic"
print(result.config.gas.wert)        # 0.7

# ダッシュボード
status = fahrer.status()
print(status["tankuhr"]["zone"])     # "green"
print(status["getriebe"])            # "Getriebe[haiku(G1), flash(G2), ...]"

# 過去の実行から学習
fahrer.trainieren()
```

## コマンドラインインターフェース

`pip install -e .` 後、`clutch` コマンドが使用可能になります：

```bash
clutch route "Fix the auth bug"      # ルーティング決定を表示（ドライラン、LLM 呼び出しなし）
clutch "Explain quantum computing"    # ワンショット：ルーティング + 実行、回答を出力
clutch run "..." --json               # 機械可読出力（他のエージェント向け）
clutch chat                           # インタラクティブ REPL
clutch models [--json]                # 全ギア（モデル）を一覧表示
clutch stats                          # 使用量 / 予算 / ヘルスダッシュボード
clutch config <key> [value]           # CLI 設定を読み取り/設定
clutch keys set MOONSHOT_API_KEY      # API キーを保存（非表示入力；値は表示されない）
clutch keys list                      # 保存済みキー名を一覧表示（値は非表示）
clutch serve --web                    # Web UI を起動（要：pip install -e ".[web]"）
```

3 つの使用モード：**コンソール**（人間向け）、**Web UI**（人間向け、グラフィカル）、**CLI/API**（他の LLM/エージェントが `--json` または OpenAI 互換 Web エンドポイントでタスクをルーティング）。

## API キーと認証情報

clutch は以下の順序でキーを解決します（最初の空でない値が優先）：

1. 環境変数（例：`MOONSHOT_API_KEY`）— CI/サーバーで推奨
2. clutch ストア `~/.clutch/credentials.json`（`clutch keys set` 経由、ファイルモード 0600）
3. `~/.credentials/<name>` ファイル（兄弟ツールとの相互運用）

値は表示、ログ記録、コミットされることはありません。

## 設定

デフォルト設定は `clutch/config/` にあり、編集可能なインストールおよび wheels が同じバンドルされたルーティングデフォルトを使用します。プロジェクト固有の上書きを行う場合は、独自の `config/` フォルダを含む `base_dir` を `Fahrer` に渡してください。

| ファイル | 用途 |
|------|---------|
| `kupplung.json` | グローバル設定（ドライバーのデフォルト、スウォーム制限、予算） |
| `getriebe.json` | 全ギア + プロバイダーマッピング |
| `strecken.json` | コースタイプからギア/アクセルへのマッピング |
| `fitness_criteria.json` | 学習エンジンのしきい値 |

### 予算ゾーン

| ゾーン | 使用率 | 使用可能なギア |
|------|-------|--------------|
| 緑 | 0--30% | 全て（G1--G5） |
| 黄 | 30--60% | G1--G3 |
| 橙 | 60--80% | G1--G2 のみ |
| 赤 | 80--100% | なし（予算枯渇） |

## 対応プロバイダー

| プロバイダー | モデル | ローカル |
|----------|--------|-------|
| **Anthropic** | Claude Haiku、Sonnet、Opus | いいえ |
| **Google** | Gemini Flash、Pro | いいえ |
| **Ollama** | Qwen、Mistral など（ローカル・リモート） | はい |
| **Claude Code** | サブプロセス経由（CLI セッション） | はい |
| **Kimi (Moonshot)** | `kimi-k2.7-code`、`kimi-k2.6`（OpenAI 互換 API）；`kimi-cli`/`kimi-code` CLI；Ollama Cloud | API / CLI |
| **OpenAI 互換** | 任意の `/v1/chat/completions` エンドポイント（`base_url` を設定） | いいえ |

## 実行パターン

- **単一** — 1 モデル、1 タスク
- **コンボイ（Kolonne）** — 順次チェーン、N の出力が N+1 の入力に
- **チーム** — 並列特化 Worker、結果をマージ
- **スウォーム** — 大規模並列マイクロタスク（例：Haiku × 20）、その後集約

## プロジェクト構成

```
clutch/
+-- clutch/
|   +-- __init__.py
|   +-- fahrer.py          # オーケストレーター
|   +-- strecke.py         # タスク分析
|   +-- getriebe.py        # モデルレジストリ
|   +-- kupplung.py        # モデル切り替え
|   +-- motorblock.py      # 統一 API 層
|   +-- gas_bremse.py      # 推論レベル
|   +-- fahrtenbuch.py     # SQLite メトリクス
|   +-- bordcomputer.py    # ヘルスモニター
|   +-- tankuhr.py         # 予算追跡
|   +-- tacho.py           # メトリクス
|   +-- fahrschule.py      # 学習エンジン
|   +-- patterns/
|       +-- kolonne.py     # チェーンパターン
|       +-- team.py        # 並列パターン
|       +-- schwarm.py     # スウォームパターン
|       +-- hybrid.py      # ハイブリッドパターン
|   +-- config/
|       +-- kupplung.json
|       +-- getriebe.json
|       +-- strecken.json
|       +-- fitness_criteria.json
+-- tests/
|   +-- test_clutch.py
|   +-- test_learning.py
|   +-- test_patterns.py
|   +-- test_route.py
+-- data/                  # ランタイムデータ（追跡対象外）
```

## テスト

```bash
pip install -e . pytest
pytest -q
```

Pytest は `tests/` のみを収集するよう設定されています。`demo.py`、`live_test.py`、`claude_code_test.py` などルートレベルのスクリプトは手動のプロバイダー確認用です。

## コントリビューション

ガイドラインは [CONTRIBUTING.md](CONTRIBUTING.md) を参照してください。
ドイツ語の自動車 API 用語については [GLOSSARY.md](GLOSSARY.md) を参照してください。

## ライセンス

MIT ライセンス。詳細は [LICENSE](LICENSE) をご覧ください。

---

## 免責事項 / Haftung

本プロジェクトは、BGB（ドイツ民法典）第 516 条以降の意味における**無償のオープンソース寄贈**です。作者の責任は **BGB 第 521 条**に基づき、**故意および重大な過失**に限定されます。補足として、GPL-3.0 / MIT / Apache-2.0 の第 15〜16 条（選択したライセンスによる）の免責条項が適用されます。

利用は自己責任で行ってください。メンテナンスの約束、可用性の保証、エラーのなさや特定の目的への適合性の保証は一切ありません。

This project is an unpaid open-source donation. Liability is limited to intent and gross negligence (§ 521 German Civil Code). Use at your own risk. No warranty, no maintenance guarantee, no fitness-for-purpose assumed.
