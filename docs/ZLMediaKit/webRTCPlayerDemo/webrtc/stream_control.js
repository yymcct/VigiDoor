/**
 * 推流控制模块
 * 用于控制华为云 IoT 推流服务的启动和停止
 */

(function(window) {
  'use strict';

  // 推流控制服务配置
  const STREAM_CONTROL_CONFIG = {
    baseUrl: 'http://localhost:5002',
    deviceId: 'VIGIDOOR_7c3a41081017190d_RPI',
    rtmpUrl: 'rtsp://192.168.38.166:8554/live/VIGIDOOR_7c3a41081017190d_RPI'
  };

  /**
   * 推流控制类
   */
  class StreamController {
    constructor(config) {
      this.config = config;
    }

    /**
     * 发送开始推流指令
     * @returns {Promise} 返回请求结果
     */
    async startStream() {
      const url = `${this.config.baseUrl}/api/v1/stream/start`;
      const payload = {
        device_id: this.config.deviceId,
        rtmp_url: this.config.rtmpUrl
      };

      try {
        console.log('发送开始推流指令:', payload);
        
        const response = await $.ajax({
          url: url,
          type: 'POST',
          contentType: 'application/json',
          data: JSON.stringify(payload),
          timeout: 10000
        });

        console.log('开始推流响应:', response);
        return {
          success: true,
          data: response
        };
      } catch (error) {
        console.error('开始推流失败:', error);
        return {
          success: false,
          error: error.responseJSON || error.statusText || '请求失败'
        };
      }
    }

    /**
     * 发送停止推流指令
     * @returns {Promise} 返回请求结果
     */
    async stopStream() {
      const url = `${this.config.baseUrl}/api/v1/stream/stop`;
      const payload = {
        device_id: this.config.deviceId
      };

      try {
        console.log('发送停止推流指令:', payload);
        
        const response = await $.ajax({
          url: url,
          type: 'POST',
          contentType: 'application/json',
          data: JSON.stringify(payload),
          timeout: 10000
        });

        console.log('停止推流响应:', response);
        return {
          success: true,
          data: response
        };
      } catch (error) {
        console.error('停止推流失败:', error);
        return {
          success: false,
          error: error.responseJSON || error.statusText || '请求失败'
        };
      }
    }

    /**
     * 检查服务健康状态
     * @returns {Promise} 返回健康检查结果
     */
    async checkHealth() {
      const url = `${this.config.baseUrl}/health`;

      try {
        const response = await $.ajax({
          url: url,
          type: 'GET',
          timeout: 5000
        });

        console.log('健康检查响应:', response);
        return {
          success: true,
          data: response
        };
      } catch (error) {
        console.error('健康检查失败:', error);
        return {
          success: false,
          error: error.responseJSON || error.statusText || '服务不可用'
        };
      }
    }
  }

  // 创建全局实例
  window.streamController = new StreamController(STREAM_CONTROL_CONFIG);

  // 导出配置，方便外部修改
  window.STREAM_CONTROL_CONFIG = STREAM_CONTROL_CONFIG;

})(window);
