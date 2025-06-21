openapi: 3.0.3
info:
  title: lava.top Public API
  version: 1.16.0
security:
  - ApiKeyAuth: [ ]

paths:
  /api/v1/feed:
    get:
      tags:
        - Products
      summary: Лента продуктов и постов
      deprecated: true
      security:
        - ApiKeyAuth: [ ]
      parameters:
        - in: query
          required: false
          name: contentCategories
          description: фильтрация по типу контента
          schema:
            $ref: '#/components/schemas/FeedItemType'
        - in: query
          required: false
          name: productTypes
          description: фильтрация по типу продукта
          schema:
            $ref: '#/components/schemas/ProductType'
        - in: query
          required: false
          name: page
          description: Номер страницы
          schema:
            format: integer
        - in: query
          required: false
          name: size
          description: Количество элементов на странице
          schema:
            format: integer
      responses:
        200:
          description: список постов и продуктов
          content:
            application/json:
              schema:
                type: object
                description: Страница элементов
                properties:
                  items:
                    type: array
                    description: Элементы страницы
                    items:
                      properties:
                        type:
                          $ref: "#/components/schemas/FeedItemType"
                        data:
                          $ref: "#/components/schemas/ProductItemDto"
                  total:
                    type: number
                  page:
                    type: number
                  size:
                    type: number

  /api/v1/invoice:
    post:
      deprecated: true
      security:
        - ApiKeyAuth: [ ]
      tags:
        - Invoices
      summary: Создание контракта на покупку контента. Устарел. Новый метод - /api/v2/invoice
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/InvoiceRequestDto'
      responses:
        201:
          description: Возвращает описание созданного контракта
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/InvoicePaymentParamsResponse'
        404:
          description: Продукт с таким идентификатором оффера не существует
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
    get:
      summary: Получение продажи партнёра. Устарел, используйте новый рут - GET /api/v1/invoices/{id}
      deprecated: true
      tags:
        - Products
      parameters:
        - in: query
          name: id
          description: Идентификатор контракта
          schema:
            type: string
            format: uuid
      responses:
        200:
          description: Продажа партнёра
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/InvoicePaymentParamsResponse'
        404:
          description: Продажа с таким id не найдена
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
        401:
          description: Пользователь неавторизован

  /api/v2/invoice:
    post:
      security:
        - ApiKeyAuth: [ ]
      tags:
        - Invoices
      summary: Создание контракта на покупку контента (аналогичен /api/v1/invoice)
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/InvoiceRequestDto'
            examples:
              product_rub_purchase_min_fields:
                summary: Пример покупки продукта (не подписки) через RUB c минимальным набором полей
                description: > 
                  paymentMethod не передан, значит по умолчанию будет использован BANK131 в качестве платежного метода. 
                  Поле periodicity также не передано и т.к. продукт является не подпиской - по умолчанию будет использован ONE_TIME значение
                value:
                  email: "client@gmail.com"
                  offerId: "836b9fc5-7ae9-4a27-9642-592bc44072b7"
                  currency: "RUB"

              product_usd_purchase:
                summary: Пример покупки продукта (не подписки) через USD c явной передачей периодичности
                description: >
                  paymentMethod не передан, значит по умолчанию будет использован UNLIMINT в качестве платежного метода
                value:
                  email: "client@gmail.com"
                  offerId: "836b9fc5-7ae9-4a27-9642-592bc44072b7"
                  currency: "USD"
                  periodicity: "ONE_TIME"

              product_eur_purchase:
                summary: Пример покупки продукта (не подписки) через EUR c явной передачей языка пользователя
                description: >
                  paymentMethod не передан, значит по умолчанию будет использован UNLIMINT в качестве платежного метода.
                  Язык пользователя выставлен на английский. Он будет учитываться при отправки нотификаций и писем на почту.
                  Если язык не передан, то по умолчанию используется английский
                value:
                  email: "client@gmail.com"
                  offerId: "836b9fc5-7ae9-4a27-9642-592bc44072b7"
                  currency: "EUR"
                  buyerLanguage: "EN"

              product_eur_purchase_paypal:
                summary: Пример покупки продукта (не подписки) через EUR (PAYPAL)
                description: >
                  Т.к. покупка осуществляется в валюте, то возможен вариант покупки продукта через PAYPAL
                value:
                  email: "client@gmail.com"
                  offerId: "836b9fc5-7ae9-4a27-9642-592bc44072b7"
                  currency: "EUR"
                  paymentMethod: "PAYPAL"

              product_usd_purchase_stripe:
                summary: Пример покупки продукта (не подписки) через USD (STRIPE)
                description: >
                  Т.к. покупка осуществляется в валюте, то возможен вариант покупки продукта через STRIPE
                value:
                  email: "client@gmail.com"
                  offerId: "836b9fc5-7ae9-4a27-9642-592bc44072b7"
                  currency: "USD"
                  paymentMethod: "STRIPE"

              product_purchase_with_utm:
                summary: Пример покупки продукта с передачей UTM-меток
                description: >
                  При совершении покупки пользователем, есть возможность передать UTM-метки
                value:
                  email: "client@gmail.com"
                  offerId: "836b9fc5-7ae9-4a27-9642-592bc44072b7"
                  currency: "EUR"
                  clientUtm:
                    utm_source: "google"
                    utm_medium: "cpc"
                    utm_campaign: "summer_sale"
                    utm_term: "running_shoes"
                    utm_content: "homepage_banner"

              subscription_usd_purchase:
                summary: Пример покупки подписки через USD (PAYPAL)
                description: Оформление подписки осуществляется с ежемесячным списанием (см. параметр periodicity) через PayPal
                value:
                  email: "client@gmail.com"
                  offerId: "836b9fc5-7ae9-4a27-9642-592bc44072b7"
                  periodicity: "MONTHLY"
                  currency: "USD"
                  paymentMethod: "PAYPAL"
                  buyerLanguage: "EN"

              subscription_eur:
                summary: Пример покупки подписки через EUR (UNLIMINT)
                value:
                  email: "client@gmail.com"
                  offerId: "836b9fc5-7ae9-4a27-9642-592bc44072b7"
                  periodicity: "PERIOD_90_DAYS"
                  currency: "EUR"
                  buyerLanguage: "EN"
                  paymentMethod: "UNLIMINT"

              subscription_usd_purchase_with_utm:
                summary: Пример покупки подписки c передачей UTM-меток
                description: >
                  Оформление подписки осуществляется со списанием каждые 180 дней (см. параметр periodicity) через PayPal.
                  В примере показано, как можно передавать UTM-метки
                value:
                  email: "client@gmail.com"
                  offerId: "836b9fc5-7ae9-4a27-9642-592bc44072b7"
                  periodicity: "PERIOD_180_DAYS"
                  currency: "USD"
                  buyerLanguage: "EN"
                  paymentMethod: "PAYPAL"
                  clientUtm:
                    utm_source: "google"
                    utm_medium: "cpc"
                    utm_campaign: "summer_sale"
                    utm_term: "running_shoes"
                    utm_content: "homepage_banner"

      responses:
        201:
          description: Возвращает описание созданного контракта
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/InvoicePaymentParamsResponse'
        404:
          description: Продукт с таким идентификатором оффера не существует
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

  /api/v1/invoices:
    get:
      security:
        - ApiKeyAuth: [ ]
      tags:
        - Invoices
      summary: Получение страницы контрактов API-ключа, использованного в запросе
      parameters:
        - in: query
          name: beginDate
          required: false
          description: >
            Параметр для поиска от переданной даты (UTC+0). Если контракт в состоянии in-progress,
            то учитывается дата создания контракта вместо даты исполнения
          schema:
            type: string
            format: date-time
        - in: query
          name: endDate
          required: false
          description: >
            Параметр для поиска до переданной даты (UTC+0). Если контракт в состоянии in-progress,
            то учитывается дата создания контракта вместо даты исполнения
          schema:
            type: string
            format: date-time
        - in: query
          name: buyerEmail
          required: false
          description: >
            Поиск по почте покупателя (на момент покупки). Работает поиск по шаблону
            (в т.ч. по полному совпадению)
          schema:
            type: string
        - in: query
          name: currencies
          required: false
          description: Валюта, в которой был инициирован контракт
          schema:
            type: array
            items:
              $ref: '#/components/schemas/CurrencyDto'
        - in: query
          name: last4CardDigits
          required: false
          description: >
            Последние 4 цифры карты покупателя. Работает поиск по шаблону, так и по полному совпадению
          schema:
            type: string
        - in: query
          name: productName
          required: false
          description: >
            Поиск по названию продукта/уровню подписки. Работает поиск по шаблону,
            так и по полному совпадению
          schema:
            type: string
        - in: query
          name: invoiceTypes
          required: false
          description: >
            Поиск по типу контракта. Если не передано, то по умолчанию - продажи продуктов и подписок
          schema:
            type: array
            items:
              $ref: '#/components/schemas/InvoiceType'
        - in: query
          name: invoiceStatuses
          required: false
          description: >
            Статус контрактов. Если не передано, то по умолчанию - только успешные (completed)
          schema:
            type: array
            items:
              $ref: '#/components/schemas/InvoiceStatus'
        - in: query
          name: page
          required: false
          description: Номер страницы
          schema:
            type: integer
            default: 1
        - in: query
          name: size
          required: false
          description: Размер страницы
          schema:
            type: integer
            default: 20
      responses:
        '200':
          description: Страница контрактов переданного API-ключа
          content:
            application/json:
              schema:
                type: object
                description: Страница с контрактами
                properties:
                  items:
                    type: array
                    description: Элементы страницы
                    items:
                      $ref: "#/components/schemas/InvoiceResponseV2"
                  page:
                    type: integer
                    description: Номер страницы
                  size:
                    type: integer
                    description: Количество элементов страницы
                  total:
                    type: integer
                    description: Общее количество элементов
        '400':
          description: Ошибка запроса
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
        '401':
          description: Пользователь не авторизован
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
        '403':
          description: Действие запрещено
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

  /api/v1/invoices/{id}:
    get:
      security:
        - ApiKeyAuth: [ ]
      tags:
        - Invoices
      summary: Получение контракта по идентификатору
      parameters:
        - in: path
          name: id
          required: true
          description: Идентификатор контракта
          schema:
            type: string
            format: uuid
      responses:
        '200':
          description: Контракт
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/InvoiceResponseV2"
        '400':
          description: Ошибка запроса
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
        '401':
          description: Пользователь не авторизован
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
        '403':
          description: Действие запрещено
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
        '404':
          description: Контракт не найден
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

  /api/v1/sales/:
    get:
      summary: Получение списка продаж партнёра
      tags:
        - Reports
      parameters:
        - in: query
          required: false
          name: page
          description: номер страницы
          schema:
            type: integer
        - in: query
          required: false
          name: size
          description: количество возвращаемых элементов страницы
          schema:
            type: integer
      responses:
        200:
          description: Страница с продажами партнёра получена
          content:
            application/json:
              schema:
                type: object
                description: Страница с продажами партнёра
                properties:
                  items:
                    type: array
                    description: Элементы страницы
                    items:
                      $ref: "#/components/schemas/PartnerProductDto"
                  total:
                    type: integer
                    description: Общее количество элементов
                  page:
                    type: integer
                    description: Номер текущей страницы
                  size:
                    type: integer
                    description: Максимальное количество элементов на странице
                  totalPages:
                    type: integer
                    description: Общее количество страниц
        400:
          description: Ошибка запроса
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
        401:
          description: Пользователь неавторизован
        403:
          description: Пользователь не является партнёром
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

  /api/v1/sales/{productId}:
    get:
      summary: Получение списка продаж партнёра по конкретному продукту
      tags:
        - Reports
      parameters:
        - in: path
          name: productId
          description: Идентификатор продукта
          required: true
          schema:
            type: string
            format: uuid
        - in: query
          required: false
          name: page
          description: номер страницы
          schema:
            type: integer
        - in: query
          required: false
          name: size
          description: количество возвращаемых элементов страницы
          schema:
            type: integer
        - in: query
          required: false
          name: fromDate
          description: Начало периода продаж (YYYY-MM-DDTHH:MM:SS+XX:XX)
          schema:
            type: string
            format: date
        - in: query
          required: false
          name: toDate
          description: Конец периода продаж (YYYY-MM-DDTHH:MM:SS+XX:XX)
          schema:
            type: string
            format: date
        - in: query
          required: false
          name: currency
          description: Currency ISO 4217 alphabetic code
          schema:
            $ref: '#/components/schemas/CurrencyDto'
        - in: query
          required: false
          name: status
          description: Статус продажи
          schema:
            $ref: '#/components/schemas/ContractStatusDto'
        - in: query
          required: false
          name: search
          description: Строка для поиска
          schema:
            type: string
      responses:
        200:
          description: Страница с продажами партнёра
          content:
            application/json:
              schema:
                type: object
                description: Страница истории отправок вебхуков
                properties:
                  items:
                    type: array
                    description: Элементы страницы
                    items:
                      $ref: "#/components/schemas/PartnerSaleDetailsDto"
                  total:
                    type: integer
                    description: Общее количество элементов
                  page:
                    type: integer
                    description: Номер текущей страницы
                  size:
                    type: integer
                    description: Максимальное количество элементов на странице
                  totalPages:
                    type: integer
                    description: Общее количество страниц
        400:
          description: Ошибка запроса
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
        401:
          description: Пользователь неавторизован

  /api/v1/subscriptions:
    delete:
      security:
        - ApiKeyAuth: [ ]
      tags:
        - Subscriptions
      summary: Отмена подписки на продукт
      parameters:
        - in: query
          name: contractId
          description: Идентификатор родительского контракта (parentContractId). Этот ID можно получить при первой покупке подписки (api/v2/invoice)
          required: true
          schema:
            type: string
            format: uuid
        - in: query
          name: email
          description: Почта пользователя, владеющего подпиской
          required: true
          schema:
            type: string
            format: email
      responses:
        204:
          description: Подписка успешно отменена
        400:
          description: Ошибка отмены подписки
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
        404:
          description: Подписки с таким contractId не существует
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

  /api/v2/products:
    get:
      security:
        - ApiKeyAuth: [ ]
      tags:
        - Products
      summary: Получение списка продуктов. Обновленная версия /api/v1/feed
      parameters:
        - in: query
          required: false
          name: beforeCreatedAt
          description: Дата создания до которой ищутся посты и продукты
          schema:
            type: string
            format: 'date-time'
        - in: query
          required: false
          name: contentCategories
          description: Фильтрация по типу контента
          schema:
            $ref: '#/components/schemas/FeedItemType'
        - in: query
          required: false
          name: productTypes
          description: Фильтрация по типу продукта
          schema:
            $ref: '#/components/schemas/ProductType'
        - in: query
          required: false
          name: feedVisibility
          description: Фильтрация по видимости контента
          schema:
            $ref: '#/components/schemas/FeedVisibility'
        - in: query
          required: false
          name: showAllSubscriptionPeriods
          description: Показывать цены офферов с периодичностью больше месяца или нет (для подписок)
          schema:
            type: boolean
            default: false
      responses:
        200:
          description: Список продуктов
          content:
            application/json:
              schema:
                type: object
                description: Страница постов и продуктов
                properties:
                  items:
                    type: array
                    description: Список постов и продуктов
                    items:
                      properties:
                        type:
                          $ref: "#/components/schemas/FeedItemType"
                        data:
                          oneOf:
                            - $ref: '#/components/schemas/ProductItemResponse'
                            - $ref: '#/components/schemas/PostItemResponse'
                  nextPage:
                    type: string
                    description: Ссылка на следующую страницу постов и продуктов
                    nullable: true
                    example: https://gate.lava.top/api/v2/products?beforeCreatedAt=2023-11-01T05:43:18.922Z

  /api/v2/products/{productId}:
    patch:
      security:
        - ApiKeyAuth: [ ]
      tags:
        - Products
      summary: Обновление продукта
      description: Для обновления офферов продукта нужно предоставить либо цену в 1 валюте (цены в остальных будут отображаться по курсу), либо в 3 валютах (поле prices)
      parameters:
        - in: path
          name: productId
          description: Идентификатор продукта
          required: true
          schema:
            type: string
            format: uuid
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ProductUpdateRequest'
      responses:
        200:
          description: Продукт успешно обновлен
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ProductItemResponse'
        404:
          description: Продукт не найден
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

  /api/v1/donate:
    get:
      security:
        - ApiKeyAuth: [ ]
      tags:
        - Donate
      summary: Получение ссылки на донат аккаунта
      responses:
        200:
          description: Ссылка на донат успешно получена
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/DonateResponse'

  /example-of-webhook-route-contract:
    post:
      tags:
        - Webhooks
      security:
        - BasicWebhookAuth: [ ]
        - ApiKeyWebhookAuth: [ ]
      summary: Пример API-метода, которому должен следовать сервис автора для приёма вебхуков от lava.top
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/PurchaseWebhookLog'
            examples:
              successful_purchase_webhook_payload:
                summary: Успешно оплаченный продукт (не подписка)
                value:
                  eventType: "payment.success"
                  product:
                    id: "d31384b8-e412-4be5-a2ec-297ae6666c8f"
                    title: "Тестовый продукт"
                  buyer:
                    email: "test@lava.top"
                  contractId: "7ea82675-4ded-4133-95a7-a6efbaf165cc"
                  amount: 40254.19
                  currency: "RUB"
                  timestamp: "2024-02-05T09:38:27.33277Z"
                  status: "completed"
                  errorMessage: ""

              failed_purchase_webhook_payload:
                summary: Неуспешно оплаченный продукт (не подписка)
                value:
                  eventType: "payment.failed"
                  product:
                    id: "d31384b8-e412-4be5-a2ec-297ae6666c8f"
                    title: "Тестовый продукт"
                  buyer:
                    email: "emwbwj@lava.top"
                  contractId: "7ea82675-4ded-4133-95a7-a6efbaf165cc"
                  amount: 40254.19
                  currency: "RUB"
                  timestamp: "2024-02-05T09:38:27.33277Z"
                  status: "failed"
                  errorMessage: "Payment window is opened but not completed"

              successful_subscription_webhook_payload:
                summary: Успешная оплата подписки (первый платёж)
                value:
                  eventType: "payment.success"
                  product:
                    id: "72d53efb-3696-469f-b856-f0d815748dd6"
                    title: "Тестовая подписка"
                  buyer:
                    email: "emwbwj@lava.top"
                  contractId: "c5a0cacc-3453-44b0-9532-aa492f1ba191"
                  amount: 2049.85
                  currency: "RUB"
                  timestamp: "2024-02-05T08:44:32.42176Z"
                  status: "subscription-active"
                  errorMessage: ""

              failed_subscription_webhook_payload:
                summary: Ошибка при оформлении подписки (первый платёж)
                value:
                  eventType: "payment.failed"
                  product:
                    id: "836b9fc5-7ae9-4a27-9642-592bc44072b7"
                    title: "Тестовая подписка"
                  contractId: "f4b84df8-98f6-4bac-9341-5dea5a1c3692"
                  buyer:
                    email: "zkvgsd@lava.top"
                  amount: 1340
                  currency: "RUB"
                  timestamp: "2024-10-31T13:33:32.871233Z"
                  status: "subscription-failed"
                  errorMessage: "Not sufficient funds"

              successful_subscription_recurring_webhook_payload:
                summary: Успешное продление подписки (второй, третий и т.д. платежи по подписке)
                value:
                  eventType: "subscription.recurring.payment.success"
                  product:
                    id: "72d53efb-3696-469f-b856-f0d815748dd6"
                    title: "Тестовая подписка"
                  buyer:
                    email: "emwbwj@lava.top"
                  contractId: "d41db415-ad71-4f2a-8d8c-27eefee91e66"
                  parentContractId: "c5a0cacc-3453-44b0-9532-aa492f1ba191"
                  amount: 2049.85
                  currency: "RUB"
                  timestamp: "2024-02-05T08:44:49.123932Z"
                  status: "subscription-active"
                  errorMessage: ""

              failed_subscription_recurring_webhook_payload:
                summary: Ошибка при продлении подписки (второй, третий и т.д. платежи)
                value:
                  eventType: "subscription.recurring.payment.failed"
                  product:
                    id: "72d53efb-3696-469f-b856-f0d815748dd6"
                    title: "Тестовая подписка"
                  buyer:
                    email: "emwbwj@lava.top"
                  contractId: "04f152b7-63ec-46ff-958e-8a6f5869acd6"
                  parentContractId: "c5a0cacc-3453-44b0-9532-aa492f1ba191"
                  amount: 2049.85
                  currency: "RUB"
                  timestamp: "2024-02-05T08:44:49.123932Z"
                  status: "subscription-failed"
                  errorMessage: "Payment window is opened but not completed"

              subscription_cancelled_webhook_payload:
                summary: Событие отмены подписки
                value:
                  eventType: "subscription.cancelled"
                  contractId: "04f152b7-63ec-46ff-958e-8a6f5869acd6"
                  product:
                    id: "72d53efb-3696-469f-b856-f0d815748dd6"
                    title: "Тестовая подписка"
                  buyer:
                    email: "emwbwj@lava.top"
                  cancelledAt: "2024-02-05T08:44:49.123932Z"
                  willExpireAt: "2024-03-06T08:44:49.123932Z"

      responses:
        2XX:
          description: Вебхук будет считаться доставленным (т.к. статус ответа 2ХХ)
        3XX:
          description: Вебхук будет считаться доставленным (т.к. статус ответа 3ХХ)
        4XX:
          description: >
            Вебхук будет считаться недоставленным (т.к. статус ответа 4ХХ).
            Сервис lava.top сделает ещё несколько попыток отправок (19) через следующие временные интервалы c момента отправки предыдущей попытки:
              1) 1s 
              2) 5s
              3) 15s
              4) 1m
              5) 1m
              6) 1m
              7) 1m
              8) 1m
              9) 1m
              10) 1m
              11) 1m
              12) 1m
              13) 1m
              14) 1m
              15) 1h
              16) 1h
              17) 1h
              18) 1h
              19) 1h
        5XX:
          description: >
            Вебхук будет считаться недоставленным (т.к. статус ответа 5ХХ).
            Сервис lava.top сделает ещё несколько попыток отправок (19) через следующие временные интервалы c момента отправки предыдущей попытки:
              1) 1s 
              2) 5s
              3) 15s
              4) 1m
              5) 1m
              6) 1m
              7) 1m
              8) 1m
              9) 1m
              10) 1m
              11) 1m
              12) 1m
              13) 1m
              14) 1m
              15) 1h
              16) 1h
              17) 1h
              18) 1h
              19) 1h

components:
  schemas:
    DonateResponse:
      type: object
      description: Тело доната
      properties:
        url:
          type: string
          format: url
          description: Ссылка на окно доната автора
          example: https://app.lava.top/alias?donate=open

    ProductUpdateRequest:
      type: object
      description: Тело для обновления продукта
      properties:
        offers:
          type: array
          description: Список офферов
          items:
            $ref: '#/components/schemas/UpdateOfferRequest'

    UpdateOfferRequest:
      type: object
      description: Тело для обновления оффера
      properties:
        id:
          type: string
          format: uuid
          description: Идентификатор оффера
        prices:
          type: array
          description: Список цен оффера
          items:
            $ref: '#/components/schemas/UpdatePriceRequest'
        name:
          type: string
          description: Название оффера
          nullable: true
        description:
          type: string
          description: Описание оффера
          nullable: true

    UpdatePriceRequest:
      type: object
      description: Тело для обновления цены оффера
      properties:
        amount:
          type: number
          format: double
          description: Цена
        currency:
          $ref: '#/components/schemas/CurrencyDto'

    ProductItemResponse:
      type: object
      description: Продукт
      properties:
        id:
          type: string
          format: uuid
          description: Идентификатор продукта
        title:
          type: string
          description: Заголовок продукта
          nullable: true
        description:
          type: string
          description: Описание продукта
          nullable: true
        type:
          $ref: '#/components/schemas/ProductType'
        offers:
          type: array
          description: Ценники продукта
          nullable: true
          items:
            $ref: '#/components/schemas/OfferResponse'

    PostItemResponse:
      type: object
      description: Пост
      properties:
        id:
          type: string
          format: uuid
          description: Идентификатор поста
        title:
          type: string
          description: Заголовок поста
        description:
          type: string
          description: Описание поста
          nullable: true
        body:
          type: string
          description: Тело поста
        type:
          $ref: '#/components/schemas/PostType'
        createdAt:
          type: string
          format: 'date-time'
          description: Время создание поста
        updatedAt:
          type: string
          format: 'date-time'
          description: Время когда был обновлен пост
        publishedAt:
          type: string
          format: 'date-time'
          description: Время когда был или будет опубликован пост

    OfferResponse:
      type: object
      description: Предложения для покупки продукта
      properties:
        id:
          type: string
          format: uuid
          description: Идентификатор ценового предложения
        name:
          type: string
          description: Наименование цены
          nullable: true
        description:
          type: string
          description: Описание предложения
          nullable: true
        prices:
          type: array
          description: Список цен в разных валютах
          items:
            $ref: '#/components/schemas/PriceDto'
        recurrent:
          $ref: '#/components/schemas/RecurrentDto'

    InvoiceRequestDto:
      type: object
      description: Описание покупки контента
      properties:
        email:
          description: Почта покупателя
          type: string
        offerId:
          description: Идентификатор цены
          type: string
          format: uuid
        periodicity:
          $ref: '#/components/schemas/Periodicity'
        currency:
          $ref: '#/components/schemas/CurrencyDto'
        paymentMethod:
          $ref: '#/components/schemas/PaymentMethod'
        buyerLanguage:
          nullable: true
          oneOf:
            - $ref: '#/components/schemas/LanguageDto'
        clientUtm:
          $ref: '#/components/schemas/ClientUtmDto'

    InvoicePaymentParamsResponse:
      type: object
      description: Описание созданного контракта
      properties:
        id:
          description: Идентификатор контракта на покупку
          type: string
          format: uuid
        status:
          allOf:
            - $ref: '#/components/schemas/ContractStatusDto'
        amountTotal:
          $ref: '#/components/schemas/AmountTotalDto'
        paymentUrl:
          type: string
          nullable: true
          description: Ссылка на виджет оплаты продукта (пусто, если продукт бесплатный)
          example: https://payment-widget-url

    DeleteNotAllowedReason:
      type: string
      description: Причины мешающие удалить оффер
      enum:
        - HAS_SALES
        - HAS_POSTS

    RecurrentDto:
      deprecated: true
      type: string
      description: Описание повторяемости платежа. Устарел. Используйте поле periodicity в ценах оффера
      enum:
        - monthly

    PriceDto:
      type: object
      description: Сумма
      properties:
        amount:
          type: number
          format: double
          description: Значение суммы
          nullable: true
        currency:
          $ref: '#/components/schemas/CurrencyDto'
        periodicity:
          $ref: '#/components/schemas/Periodicity'

    OfferDto:
      type: object
      description: Ценник
      properties:
        id:
          type: string
          format: uuid
          description: Идентификатор ценового предложения
        prices:
          type: array
          description: Список цен в разных валютах
          items:
            $ref: '#/components/schemas/PriceDto'
        name:
          type: string
          description: Наименование цены
          nullable: true
        description:
          type: string
          description: Описание предложения
          nullable: true
        recurrent:
          $ref: '#/components/schemas/RecurrentDto'
        availablePosts:
          type: array
          description: Список идентификаторов постов для покупки
          items:
            type: string
            format: uuid
        canBeDeleted:
          type: boolean
          description: Возможность удалить
        reasons:
          description: Причины не разрещающие удалить оффер
          type: array
          items:
            $ref: '#/components/schemas/DeleteNotAllowedReason'

    Status:
      type: string
      description: Статус продукта или поста
      enum:
        - PUBLISHED

    PostType:
      type: string
      description: Тип поста
      enum:
        - LESSON
        - POST

    ModerationStatus:
      type: string
      description: Статус модерации
      enum:
        - NEW
        - REJECTED
        - APPROVED
        - BLOCKED

    ProductItemDto:
      type: object
      description: Элемент списка продуктов
      properties:
        id:
          type: string
          format: uuid
          description: Идентификатор продукта
        accountId:
          type: string
          format: uuid
          description: Идентификатор юзера, создавшего продукт
        title:
          type: string
          description: Заголовок продукта
          nullable: true
        updatedAt:
          type: string
          format: date-time
        status:
          $ref: '#/components/schemas/Status'
        moderationStatus:
          $ref: '#/components/schemas/ModerationStatus'
        type:
          $ref: '#/components/schemas/ProductType'
        offers:
          type: array
          description: Ценники продукта
          items:
            $ref: '#/components/schemas/OfferDto'

    FeedItemType:
      type: string
      description: Типы итемов для ленты
      enum:
        - POST
        - PRODUCT
      default: PRODUCT

    ProductType:
      type: string
      description: Тип продукта
      enum:
        - COURSE
        - DIGITAL_PRODUCT
        - BOOK
        - GUIDE
        - SUBSCRIPTION
        - AUDIO
        - MODS
        - CONSULTATION

    PartnerSaleDto:
      type: object
      description: Продажа партнёра
      properties:
        currency:
          allOf:
            - $ref: '#/components/schemas/CurrencyDto'
        count:
          type: integer
          description: Количество проданных экземпляров
        amountTotal:
          type: integer
          description: Общие продажи

    PartnerProductDto:
      type: object
      description: Продажа партнёра
      properties:
        productId:
          type: string
          format: uuid
          description: Идентификатор продукта
        title:
          type: string
          description: Название продукта
        status:
          type: string
          description: Статус продукта
        sales:
          items:
            $ref: '#/components/schemas/PartnerSaleDto'

    AmountTotalDto:
      type: object
      description: Продажи в валюте
      properties:
        currency:
          $ref: '#/components/schemas/CurrencyDto'
        amount:
          type: integer
          description: Значение суммы

    BuyerDto:
      type: object
      description: Покупатель продукта
      properties:
        email:
          type: string
          format: email
          description: Почта покупателя

    PartnerSaleDetailsDto:
      type: object
      description: Продажи по конкретному продукту
      properties:
        id:
          type: string
          format: uuid
          description: Идентификатор контракта
        createdAt:
          type: string
          format: date-time
          description: Дата создания
        status:
          $ref: '#/components/schemas/ContractStatusDto'
        amountTotal:
          $ref: '#/components/schemas/AmountTotalDto'
        buyer:
          $ref: '#/components/schemas/BuyerDto'

    PurchaseWebhookLog:
      type: object
      description: Тело вебхука, отправляемого партнёру, см. примеры ниже.
      properties:
        eventType:
          $ref: '#/components/schemas/WebhookEventType'
        product:
          type: object
          properties:
            id:
              type: string
              format: uuid
              description: Идентификатор продукта
            title:
              type: string
              description: Название продукта
        contractId:
          type: string
          format: uuid
          description: Идентификатор контракта на покупку
        parentContractId:
          type: string
          nullable: true
          format: uuid
          description: Идентификатор родительского контракта на покупку (не пусто только в случае рекуррентого платежа)
        buyer:
          $ref: '#/components/schemas/WebhookBuyer'
        amount:
          type: number
          description: Значение суммы
        currency:
          $ref: '#/components/schemas/CurrencyDto'
        status:
          $ref: '#/components/schemas/ContractStatusDto'
        timestamp:
          type: string
          format: date-time
          description: Дата операции
        clientUtm:
          $ref: '#/components/schemas/ClientUtmDto'
        errorMessage:
          type: string
          nullable: true
          description: Описание причины ошибки оплаты

    WebhookBuyer:
      type: object
      description: Информация о покупателе
      properties:
        email:
          type: string
          format: email
          description: Email покупателя

    ClientUtmDto:
      type: object
      description: UTM покупки
      properties:
        utm_source:
          type: string
          nullable: true
          description: Определяет источник трафика (например, Google, Facebook). Может быть пустым.
        utm_medium:
          type: string
          nullable: true
          description: Указывает средство маркетинговой кампании (например, электронная почта, CPC, баннер). Может быть пустым.
        utm_campaign:
          type: string
          nullable: true
          description: Указывает конкретное имя кампании или идентификатор (например, spring_sale, product_launch). Может быть пустым.
        utm_term:
          type: string
          nullable: true
          description: Отслеживает ключевые слова или поисковые термины для платных кампаний (например, "sneakers"). Может быть пустым.
        utm_content:
          type: string
          nullable: true
          description: Различает варианты одного и того же объявления или кампании (например, "banner_ad_A"). Может быть пустым.
      required: [ ]
      example:
        utm_source: "google"
        utm_medium: "cpc"
        utm_campaign: "summer_sale"
        utm_term: "running_shoes"
        utm_content: "homepage_banner"

    ErrorResponse:
      type: object
      description: Тело ошибки
      properties:
        error:
          type: string
          description: Описание ошибки
          example: Input fields are invalid
        details:
          type: object
          description: Детальное описание ошибки
          additionalProperties:
            type: string
            description: Детальное описание ошибки поля
          example:
            email: should be well-formed email
            password: should contain at least 8 symbols
        timestamp:
          type: string
          format: date-time
          description: Дата ошибки

    InvoiceResponseV2:
      type: object
      properties:
        id:
          type: string
          format: uuid
          description: Идентификатор контракта
        type:
          $ref: '#/components/schemas/InvoiceType'
        datetime:
          type: string
          format: date-time
          description: Время исполнения контракта (если пусто, то время создания)
        status:
          $ref: '#/components/schemas/InvoiceStatus'
        receipt:
          $ref: '#/components/schemas/InvoiceResponseV2.ReceiptResponse'
        buyer:
          $ref: '#/components/schemas/InvoiceResponseV2.BuyerResponse'
        product:
          $ref: '#/components/schemas/InvoiceResponseV2.ProductResponse'
        parentInvoice:
          $ref: '#/components/schemas/InvoiceResponseV2.ParentInvoiceResponse'
        subscriptionStatus:
          $ref: '#/components/schemas/SubscriptionStatus'
        subscriptionDetails:
          $ref: '#/components/schemas/InvoiceResponseV2.SubscriptionDetails'
        clientUtm:
          $ref: '#/components/schemas/InvoiceClientUtm'

    InvoiceResponseV2.SubscriptionDetails:
      type: object
      properties:
        expiredAt:
          type: string
          format: date-time
          nullable: true
          description: "Дата, когда истекает действие подписки"
        terminatedAt:
          type: string
          format: date-time
          nullable: true
          description: "Дата, когда доступ к подписке был закрыт"
        cancelledAt:
          type: string
          format: date-time
          nullable: true
          description: "Дата, когда была отменена подписка"

    InvoiceResponseV2.ReceiptResponse:
      type: object
      properties:
        amount:
          type: number
          format: double
          description: Сумма покупки. 0, если бесплатная
        currency:
          $ref: '#/components/schemas/CurrencyDto'
        fee:
          type: number
          format: double
          description: Комиссия

    InvoiceResponseV2.BuyerResponse:
      type: object
      properties:
        email:
          type: string
          format: email
          description: Почта покупателя на момент покупки
          example: test@gmail.com
        cardMask:
          type: string
          description: Последние 4 цифры карты покупателя
          example: "**** **** **** 1234"

    InvoiceResponseV2.ProductResponse:
      type: object
      properties:
        name:
          type: string
          description: Название продукта
          example: Урок по психологии
        offer:
          type: string
          description: Название оффера продукта
          example: Подписка на 12 мес.

    InvoiceResponseV2.ParentInvoiceResponse:
      type: object
      properties:
        id:
          type: string
          format: uuid
          description: >
            Идентификатор родительского контракта. В случае с рекуррентным
            платежом - контракт оформления подписки

    InvoiceClientUtm:
      type: object
      properties:
        utm_source:
          type: string
          nullable: true
          description: >
            Определяет источник трафика (например, Google, Facebook). Может быть пустым.
          example: google
        utm_medium:
          type: string
          nullable: true
          description: >
            Указывает средство маркетинговой кампании (например, электронная почта, CPC, баннер). Может быть пустым.
          example: cpc
        utm_campaign:
          type: string
          nullable: true
          description: >
            Указывает конкретное имя кампании или идентификатор (например, spring_sale, product_launch). Может быть пустым.
          example: summer_sale
        utm_term:
          type: string
          nullable: true
          description: >
            Отслеживает ключевые слова или поисковые термины для платных кампаний (например, "sneakers"). Может быть пустым.
          example: running_shoes
        utm_content:
          type: string
          nullable: true
          description: >
            Различает варианты одного и того же объявления или кампании (например, "banner_ad_A"). Может быть пустым.
          example: homepage_banner

    CurrencyDto:
      type: string
      description: Валюта
      enum:
        - RUB
        - USD
        - EUR

    ContractStatusDto:
      type: string
      description: Статус контракта
      enum:
        - new
        - in-progress
        - completed
        - failed
        - cancelled
        - subscription-active
        - subscription-expired
        - subscription-cancelled
        - subscription-failed

    LanguageDto:
      type: string
      description: Язык (ISO 639-1)
      enum:
        - EN
        - RU
        - ES
      default: EN

    FeedVisibility:
      type: string
      description: Видимость контента
      enum:
        - ALL
        - ONLY_VISIBLE
        - ONLY_HIDDEN
      default: ONLY_VISIBLE

    PaymentMethod:
      type: string

      description: > 
        Провайдер для платежа.
        
        Для платежей в российских рублях (RUB) доступен только BANK131, для платежей в Евро (EUR) или Долларах (USD) - UNLIMINT и PAYPAL, STRIPE. 
        STRIPE доступен только для оплаты продуктов.
        
        Если провайдер не указан при создании платежа, то для RUB будет по умолчанию использован BANK131, а для EUR и USD - UNLIMINT
      enum:
        - BANK131
        - UNLIMINT
        - PAYPAL
        - STRIPE

    Periodicity:
      type: string
      description: Периодичность оплаты
      enum:
        - ONE_TIME
        - MONTHLY
        - PERIOD_90_DAYS
        - PERIOD_180_DAYS
        - PERIOD_YEAR

    InvoiceType:
      type: string
      description: Тип контракта
      enum:
        - ONE_TIME
        - RECURRING

    InvoiceStatus:
      type: string
      description: Статус контракта
      enum:
        - NEW
        - IN_PROGRESS
        - COMPLETED
        - FAILED

    SubscriptionStatus:
      type: string
      description: Статус подписки
      enum:
        - ACTIVE
        - CANCELLED
        - FAILED

    WebhookEventType:
      type: string
      description: Тип события вебхука
      enum:
        - payment.success
        - payment.failed
        - subscription.recurring.payment.success
        - subscription.recurring.payment.failed
        - subscription.cancelled

  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer

    ApiKeyAuth:
      type: apiKey
      in: header
      name: X-Api-Key

    BasicWebhookAuth:
      type: http
      scheme: basic

    ApiKeyWebhookAuth:
      type: apiKey
      in: header
      name: X-Api-Key