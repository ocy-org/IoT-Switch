"# IoT-Switch" 
  本项目是一个物联网集成项目，OME第三方的智慧开关，第三方公司提供了OME开关-->OEM配套网关-->OME配套的业务系统，而此物联网集成项目的链路拓扑是：OME开关-->OEM配套网关-->（中国移动的）ONENET物联网平台-->政务网内网服务器-->数据推送大数据平台。
  OEM公司关键链路【OEM配套网关-->OME配套的业务系统】走的是私有协议，无法直接适配中国移动的ONENET物联网平台，此项目在【ONENET物联网平台】链路进行如下适配工作：
  - 南向接入【MQTT批量接入】(批量接口与ONENET平台完全一样)
  - 北向推送内容【POST推送到指定URL】(ONENET平台可配置相同的接口)
  并且因为OME配套的业务系统无法使用，在【政务网内网服务器】环节通过flask-web提供了web管理端，以及实现数据推送大数据平台的功能。<br>
  
## 代码架构
IOT/gateway_sim/<br>
├── ═══ 网关侧（模拟断路器网关）═══<br>
├── gen_data.py         造数据程序<br>
├── gateway.py          推送批量数据到MQTT程序：$sys/admin/gw0001/thing/pack/post (ONENET平台批量推送接口)<br>
├── config.py           网关侧共享配置<br>
├── db.py               读取sqlite表中的数据，OEM网关读取OEM开关数据之后，把数据存储在本地sqlite表中<br>
<br>
IOT/onenet_sim/<br>
├── ═══ OneNET平台模拟 ═══<br>
├── onenet_sim.py       OneNET模拟器：连MQTT订阅 pack/post 主题 → 收到网关发布的包 → 组HTTP报文POST到gov_server<br>
<br>
IOT/gov_server/<br>
├── ═══ 政务网侧（核心业务）═══<br>
├── gov_server.py       接收服务(:8000)：Flask接收OneNET推送数据<br>
├── gov_common.py       共享模块<br>
├── gov_web.py          Web管理系统<br>
IOT/gov_server/templates  html文件<br>
## 环境安装
mqtt包安装<br>
pip install paho-mqtt==1.6.1<br>
Flask包安装<br>
pip install Flask<br>

## web管理系统
<img width="1904" height="574" alt="image" src="https://github.com/user-attachments/assets/74160a5d-4acc-4d83-8c3b-0dee5468e05e" />
<img width="1895" height="875" alt="image" src="https://github.com/user-attachments/assets/5d2c07a3-6e36-4695-9604-9b4fb4802007" />
<img width="1904" height="766" alt="image" src="https://github.com/user-attachments/assets/330bdf3e-ddfd-4d42-a5d3-a36ce4bdd943" />
<img width="1899" height="526" alt="image" src="https://github.com/user-attachments/assets/8226ea69-bfd4-4dce-9de9-175eab0b5cfe" />
<img width="1899" height="401" alt="image" src="https://github.com/user-attachments/assets/7b3eb6bd-886a-40fa-b78d-2ebaf6bad049" />

