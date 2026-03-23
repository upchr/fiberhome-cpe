    def _run(self):
        """运行监听循环"""
        # 首次启动时，处理未读短信并记录所有短信 ID
        try:
            success, _ = self._client.login(self.username, self.password)
            if success:
                sms_list = self._client.get_sms_list()
                
                # 找出未读短信（接收的且未读的）
                unread_sms = [sms for sms in sms_list if not sms.is_read and not sms.is_sent]
                
                # 发送未读短信通知
                if unread_sms:
                    logger.info(f"发现 {len(unread_sms)} 条未读短信")
                    self._handle_new_sms(unread_sms)
                
                # 记录所有短信 ID（避免重复通知）
                for sms in sms_list:
                    if sms.id:
                        self._processed_sms_ids.add(sms.id)
                
                logger.info(f"已记录 {len(self._processed_sms_ids)} 条短信 ID，开始监听新短信")
                # 不登出，保持登录状态
        except Exception as e:
            logger.warning(f"初始化失败: {e}")
        
        while self._running:
            try:
                # 检查登录状态
                if not self._client.is_logged_in():
                    logger.info("尝试登录...")
                    success, message = self._client.login(self.username, self.password)
                    if not success:
                        logger.warning(f"登录失败: {message}")
                        time.sleep(self.wait_after_logout)
                        continue
                    logger.info("登录成功")
                
                # 检查新短信（每次都检查，不依赖心跳）
                sms_list = self._client.get_sms_list()
                if sms_list:
                    # 过滤出新短信（不在已处理列表中的）
                    new_sms = [sms for sms in sms_list if sms.id and sms.id not in self._processed_sms_ids]
                    if new_sms:
                        logger.info(f"发现 {len(new_sms)} 条新短信")
                        self._handle_new_sms(new_sms)
                
                # 等待下次检查
                time.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"监听出错: {e}")
                time.sleep(5)
