const token = document.querySelector<HTMLInputElement>("#token")!;
const button = document.querySelector<HTMLButtonElement>("#pair")!;
const statusElement = document.querySelector<HTMLElement>("#status")!;


button.addEventListener("click", () => {
  const value = token.value.trim();
  if (!value) {
    statusElement.textContent = "请输入配对令牌。";
    return;
  }
  button.disabled = true;
  statusElement.textContent = "正在连接…";
  chrome.runtime.sendMessage({ type: "pair", token: value }, (response) => {
    button.disabled = false;
    if (chrome.runtime.lastError) {
      statusElement.textContent = `连接失败：${chrome.runtime.lastError.message}`;
      return;
    }
    statusElement.textContent = response?.ok ? "已连接本地工作台。" : `连接失败：${response?.error ?? "未知错误"}`;
    if (response?.ok) token.value = "";
  });
});

export {};
