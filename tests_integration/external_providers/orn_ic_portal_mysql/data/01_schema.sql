
-- wp_mwai_chats table schema
-- wp_mwai_chats table schema from orn ic_portal MySQL database
-- This is the official schema that cannot be changed

CREATE TABLE `wp_mwai_chats`
(   `id` bigint NOT NULL AUTO_INCREMENT,
   `userId` bigint DEFAULT NULL,
   `ip` varchar(64) COLLATE utf8mb4_unicode_520_ci DEFAULT NULL,
   `title` varchar(64) COLLATE utf8mb4_unicode_520_ci DEFAULT NULL,
   `messages` text COLLATE utf8mb4_unicode_520_ci,
   `extra` longtext COLLATE utf8mb4_unicode_520_ci,
   `botId` varchar(64) COLLATE utf8mb4_unicode_520_ci DEFAULT NULL,
   `chatId` varchar(64) COLLATE utf8mb4_unicode_520_ci NOT NULL,
   `threadId` varchar(64) COLLATE utf8mb4_unicode_520_ci DEFAULT NULL,
   `storeId` varchar(64) COLLATE utf8mb4_unicode_520_ci DEFAULT NULL,
   `created` datetime NOT NULL,
   `updated` datetime NOT NULL,
   PRIMARY KEY (`id`),   KEY `chatId` (`chatId`)
) ENGINE=InnoDB AUTO_INCREMENT=30 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_520_ci
