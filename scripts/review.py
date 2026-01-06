#!/usr/bin/env python3
import os
import sys
import subprocess
from google import genai  # 新しいSDKのインポート
from github import Github, Auth

def get_diff(base_ref, head_ref):
    """
    Gitの差分を取得します。
    """
    # ベースブランチの情報を取得
    try:
        subprocess.run(["git", "fetch", "origin", base_ref], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        print(f"Error fetching base ref: {e}")
        sys.exit(1)

    # 差分に含めないファイルパターン
    exclude_patterns = [
        ":(exclude)composer.lock",
        ":(exclude)package-lock.json",
        ":(exclude)yarn.lock",
        ":(exclude)pnpm-lock.yaml",
        ":(exclude)public/build/*",
        ":(exclude)public/vendor/*",
        ":(exclude)vendor/*",
        ":(exclude)node_modules/*",
        ":(exclude)storage/*",
        ":(exclude)*.min.js",
        ":(exclude)*.min.css",
        ":(exclude)*.map",
        ":(exclude)*.svg",
        ":(exclude)*.png",
        ":(exclude)*.jpg",
        ":(exclude)*.jpeg",
        ":(exclude)*.ico",
        ":(exclude)*.woff",
        ":(exclude)*.woff2"
    ]

    # git diffコマンドの構築
    cmd = ["git", "diff", f"origin/{base_ref}...HEAD", "--"] + exclude_patterns

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding='utf-8')
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error running git diff: {e}")
        sys.exit(1)

def main():
    # 環境変数の取得
    api_key = os.environ.get("GEMINI_API_KEY")
    github_token = os.environ.get("GITHUB_TOKEN")
    repo_name = os.environ.get("REPO_NAME")
    pr_number_str = os.environ.get("PR_NUMBER")

    # 必須変数のチェック
    if not all([api_key, github_token, repo_name, pr_number_str]):
        print("Error: Missing environment variables.")
        sys.exit(1)

    try:
        pr_number = int(pr_number_str)
    except ValueError:
        print("Error: PR_NUMBER must be an integer.")
        sys.exit(1)

    # GitHub APIクライアントの初期化
    auth = Auth.Token(github_token)
    g = Github(auth=auth)

    try:
        repo = g.get_repo(repo_name)
        pr = repo.get_pull(pr_number)
    except Exception as e:
        print(f"Error fetching PR info from GitHub: {e}")
        sys.exit(1)

    # 差分テキストの取得
    diff_text = get_diff(pr.base.ref, pr.head.ref)

    if not diff_text.strip():
        print("No significant changes found to review.")
        return

    # --- 新しいSDK (google-genai) の初期化 ---
    client = genai.Client(api_key=api_key)

    # プロンプトの構築（テックリード仕様）
    prompt = f"""
あなたは、**モダンなWeb開発（Laravel, WordPress, React, Tailwind CSS, HTML/CSS）に精通したテックリード**です。
チームにはジュニアエンジニアが多いため、コードの安全性だけでなく、**「モダンな記述法」「可読性」「冗長性の排除」**について教育的なレビューを行うことがあなたの使命です。

以下のプルリクエストのコード差分（`diff`）を確認し、対象ファイルの種類（静的LP、バックエンド、フロントエンド等）を自動的に判断してレビューしてください。

**【重点レビュー項目】**

**1. 🔰 ジュニアエンジニア育成・コード品質（最優先）**
   - **脱・レガシー記述**:
     - PHP: 古い構文（`array()` → `[]`）、型宣言の欠如、モダンな機能（Null合体演算子 `??`、Match式など）の不使用。
     - JS: `var` の使用（`const`/`let`への修正）、不要なjQuery（Vanilla JSで書けるもの）。
   - **冗長性の排除**: 無駄な `if/else` ネスト、DRY原則違反（コピペコード）、早期リターン（Early Return）の推奨。
   - **ハードコーディング**: マジックナンバーや環境依存の値を直接書いていないか。

**2. 🎨 フロントエンド (HTML/CSS/Tailwind/JS/React)**
   - **HTML/LP**: セマンティックなマークアップ（`div`漬けの回避）、アクセシビリティ（`alt`属性、適切な`aria`ラベル）、スマホ表示時の崩れ懸念。
   - **Tailwind CSS**: クラスの羅列が適切か（`@apply`の乱用防止）、設定ファイルに書くべき色のハードコード。
   - **React**: 不必要な再レンダリング、`useEffect`依存配列のミス、Propsのバケツリレー。

**3. 🐘 バックエンド (Laravel/WordPress/PHP)**
   - **Laravel**: N+1問題、Fat Controller、バリデーションロジックの分離（FormRequest推奨）、Mass Assignment対策。
   - **WordPress**: エスケープ漏れ（`esc_html`, `esc_url`等）によるXSS脆弱性、Nonceチェック漏れ、サニタイズ不足。
   - **SQL**: 生SQLの記述、インデックスを無視した重いクエリ。

**4. 🛡️ セキュリティ全般**
   - XSS, CSRF, SQLインジェクションの可能性。
   - 認証・認可の不備。
   - 機密情報（APIキーなど）のコミット混入。

**【出力形式】**
Markdown形式で日本語で出力してください。
- 冒頭に **「## 🤖 AI Tech Lead Review」** として、変更内容の概要と全体的な品質評価（S/A/B/C）を記述してください。
- 指摘事項は **「📂 ファイル名」** ごとにブロックを分けてください。
- 指摘がないファイルは省略してください。
- 各指摘には重要度アイコンを付けてください。
    - 🔥 **必須** (バグ、セキュリティ、重大なアンチパターン)
    - ⚠️ **改善** (モダンな書き方への修正、可読性向上、パフォーマンス)
    - ℹ️ **教育** (ジュニア向けの豆知識、より良い書き方の提案)
- **【重要】** 指摘をする際は、**「なぜその書き方が良くないのか」**を優しく解説し、**「修正後のモダンなコード例」**を必ず提示してください。

**【コード差分】**
```diff
{diff_text[:800000]}
```
"""
    try:
        # --- 新しいSDKでの生成呼び出し ---
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=prompt
        )

        review_body = response.text

        # GitHubのPRにコメントを投稿
        pr.create_issue_comment(review_body)
        print(f"Review comment posted to PR #{pr_number}.")

    except Exception as e:
        print(f"Error during Gemini generation or GitHub posting: {e}")
        sys.exit(1)

if __name__ == "__main__":main()
