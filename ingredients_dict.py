# ingredients_dict.py
# Список популярных ингредиентов для кулинарии (на русском, в нижнем регистре)

KNOWN_INGREDIENTS = set([
    # Овощи
    'лук', 'луковица', 'чеснок', 'морковь', 'картофель', 'картошка', 'помидор', 'томат', 'огурец',
    'перец', 'перец болгарский', 'перец чили', 'капуста', 'белокочанная капуста', 'краснокочанная капуста',
    'савойская капуста', 'пекинская капуста', 'цветная капуста', 'брокколи', 'шпинат', 'салат', 'айсберг',
    'свекла', 'баклажан', 'кабачок', 'цукини', 'тыква', 'редис', 'редька', 'пастернак', 'репа',
    'зелень', 'петрушка', 'укроп', 'кинза', 'базилик', 'сельдерей', 'розмарин', 'тимьян', 'мята',
    'руккола', 'щавель', 'крапива', 'морковка',

    # Бобовые и крупы
    'фасоль', 'красная фасоль', 'белая фасоль', 'чечевица', 'горох', 'нут', 'рис', 'бурый рис', 'жасминовый рис',
    'гречка', 'перловка', 'пшено', 'овсянка', 'манка', 'ячневая крупа', 'булгур', 'кускус',

    # Макароны и тесто
    'макароны', 'спагетти', 'фетучини', 'паста', 'лапша', 'яичная лапша', 'вермишель', 'пельмени', 'вареники',
    'тесто', 'слоёное тесто', 'дрожжевое тесто', 'песочное тесто',

    # Молочные продукты
    'молоко', 'топлёное молоко', 'кефир', 'йогурт', 'ряженка', 'сливки', 'творог', 'сыр', 'моцарелла',
    'пармезан', 'бри', 'адыгейский сыр', 'масло', 'сливочное масло', 'растительное масло', 'оливковое масло',
    'топлёное масло', 'сметана', 'сгущёнка',

    # Яйца
    'яйцо', 'яичный белок', 'яичный желток', 'перепелиное яйцо',

    # Хлеб и выпечка
    'хлеб', 'чёрный хлеб', 'белый хлеб', 'батон', 'булка', 'булочка', 'лаваш', 'чиабатта',
    'багет', 'пита', 'сухари', 'крекер',

    # Мясо и птица
    'курица', 'куриная грудка', 'куриное бедро', 'куриное филе', 'голень', 'индейка', 'утка', 'гусь',
    'говядина', 'фарш говяжий', 'свинина', 'свиной фарш', 'баранина', 'кролик', 'печень', 'печень куриная',
    'печень говяжья', 'сердце', 'язык', 'паштет', 'колбаса', 'сосиска', 'ветчина', 'бекон', 'салями',

    # Рыба и морепродукты
    'рыба', 'лосось', 'семга', 'форель', 'треска', 'минтай', 'хек', 'щука', 'карп', 'окунь',
    'тунец', 'сардина', 'анчоусы', 'кета', 'осётр', 'сельдь', 'кальмар', 'креветка', 'мидии', 'устрицы',
    'краб', 'крабовые палочки', 'икра',

    # Фрукты и ягоды
    'яблоко', 'груша', 'банан', 'киви', 'апельсин', 'мандарин', 'лимон', 'лайм', 'ананас', 'виноград',
    'гранат', 'арбуз', 'дыня', 'персик', 'нектарин', 'слива', 'абрикос', 'вишня', 'черешня',
    'клубника', 'малина', 'ежевика', 'черника', 'голубика', 'смородина', 'крыжовник',

    # Орехи и сухофрукты
    'орех', 'грецкий орех', 'миндаль', 'фундук', 'арахис', 'фисташки', 'кешью', 'семечки',
    'изюм', 'курага', 'чернослив', 'финики', 'инжир',

    # Сладости
    'шоколад', 'молочный шоколад', 'чёрный шоколад', 'горький шоколад', 'белый шоколад', 'конфета',
    'вафли', 'печенье', 'пряник', 'кекс', 'торт', 'пирог', 'пирожок', 'блин', 'оладьи', 'мёд', 'варенье',
    'мармелад', 'зефир', 'ирис', 'пастила',

    # Приправы и специи
    'соль', 'морская соль', 'сахар', 'ваниль', 'перец', 'чёрный перец', 'красный перец',
    'паприка', 'чили', 'куркума', 'имбирь', 'карри', 'зира', 'корица', 'мускатный орех', 'гвоздика',
    'лавровый лист', 'уксус', 'яблочный уксус', 'винный уксус', 'соевый соус', 'горчица', 'кетчуп',
    'майонез', 'томатная паста',

    # Выпечка и десерты
    'мука', 'пшеничная мука', 'кукурузная мука', 'ржаная мука', 'разрыхлитель', 'сода', 'дрожжи',
    
    # Напитки
    'вода', 'минеральная вода', 'газировка', 'сок', 'апельсиновый сок', 'яблочный сок', 'компот',
    'морс', 'чай', 'чёрный чай', 'зелёный чай', 'кофе', 'эспрессо', 'капучино', 'латте',

    # Алкоголь
    'вино', 'красное вино', 'белое вино', 'пиво', 'шампанское', 'водка', 'коньяк', 'ром',
    'текила', 'джин', 'виски', 'ликёр', 'бренди', 'шнапс',
])