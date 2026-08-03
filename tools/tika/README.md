# Apache Tika 本地测试服务

完整后端测试包含一项真实 DOCX 解析验证，需要 Apache Tika 3.3.1 在
`127.0.0.1:9998` 监听。

将 `tika-server-standard-3.3.1.jar` 放入本目录。JAR 属于下载的第三方运行时，
不会纳入 Git；仓库只保存版本、SHA-512 和启动脚本。

在仓库根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File tools/tika/start-tika.ps1
```

启动脚本会先验证 JAR 的 SHA-512。校验失败时不会启动服务。
