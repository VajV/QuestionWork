# RPG Feature Plans Index

Набор отдельных implementation-планов для RPG-направления QuestionWork.
Каждый документ готовит одну фичу к старту разработки и опирается на текущие файлы проекта.

## Порядок запуска

1. [01-classes-gameplay-bonuses.md](c:\QuestionWork\docs\superpowers\plans\2026-03-23-rpg-feature-plans\01-classes-gameplay-bonuses.md)
2. [02-skill-tree-expansion.md](c:\QuestionWork\docs\superpowers\plans\2026-03-23-rpg-feature-plans\02-skill-tree-expansion.md)
3. [03-seasonal-lore-world-map.md](c:\QuestionWork\docs\superpowers\plans\2026-03-23-rpg-feature-plans\03-seasonal-lore-world-map.md)
4. [04-guilds-and-shared-progression.md](c:\QuestionWork\docs\superpowers\plans\2026-03-23-rpg-feature-plans\04-guilds-and-shared-progression.md)
5. [05-coop-raid-quests.md](c:\QuestionWork\docs\superpowers\plans\2026-03-23-rpg-feature-plans\05-coop-raid-quests.md)
6. [06-equipment-artifacts-cosmetics.md](c:\QuestionWork\docs\superpowers\plans\2026-03-23-rpg-feature-plans\06-equipment-artifacts-cosmetics.md)
7. [07-pve-training-quests.md](c:\QuestionWork\docs\superpowers\plans\2026-03-23-rpg-feature-plans\07-pve-training-quests.md)
8. [08-factions-and-alignment.md](c:\QuestionWork\docs\superpowers\plans\2026-03-23-rpg-feature-plans\08-factions-and-alignment.md)
9. [09-reputation-as-rpg-stats.md](c:\QuestionWork\docs\superpowers\plans\2026-03-23-rpg-feature-plans\09-reputation-as-rpg-stats.md)
10. [10-legendary-quest-chains.md](c:\QuestionWork\docs\superpowers\plans\2026-03-23-rpg-feature-plans\10-legendary-quest-chains.md)
11. [11-differentiated-card-drops-guild-vs-solo.md](c:\QuestionWork\docs\superpowers\plans\2026-03-23-rpg-feature-plans\11-differentiated-card-drops-guild-vs-solo.md)

## Рекомендуемая очередность на завтра

Утро:
- 01 классы
- 02 дерево навыков
- 09 репутация

После обеда:
- 03 сезонный мир
- 08 фракции
- 06 артефакты
- 11 карточный дроп для guild и solo

Следующая волна:
- 04 гильдии
- 07 PvE
- 05 рейды
- 10 легендарные цепочки
- расширение персональной коллекции карт

## Принцип

Каждый план написан в формате implementation handoff:
- цель
- архитектурный подход
- точные файлы
- пошаговые задачи
- тестирование
- definition of done

## Новый план по картам

План `11-differentiated-card-drops-guild-vs-solo.md` добавляет отдельную продуктовую механику:
- участники гильдии получают карты чаще
- соло-игроки получают карты реже
- соло-игроки получают более ценные карточные пулы

Базовая продуктовая гипотеза для старта:
- guild members: шанс дропа 10%
- solo players: шанс дропа 5%
- solo pool: лучшее среднее качество или более редкие семейства карт
