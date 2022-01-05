import discord
from main import *
import random

NAUGHTY = {
    "pokemon": 65,
    "pokecoins": 10,
    "shards": 10,
    "rare": 10,
    "nothing": 5,
}

NICE = {
    "event": 89,
    "redeem": 10,
    "shiny": 1,
}
NAUGHTY = list(NAUGHTY.keys()), list(NAUGHTY.values())
NICE = list(NICE.keys()), list(NICE.values())

class Test(slash.ApplicationCog):
    def __init__(self, bot):
        self.bot = bot

    display_emoji = "🧪"
    
    @commands.max_concurrency(1, commands.BucketType.user)
    @commands.command(aliases=("o",), enabled=False)
    async def open(self, ctx, box_type: str = "", amt: int = 1):
        """Open a box"""

        if amt <= 0:
            return await ctx.send("Nice try...")

        if amt > 15:
            return await ctx.send("You can only open 15 event boxes at once!")
        
        box_type = box_type.lower()
        if box_type not in {"nice", "naughty"}:
            return await ctx.send("Please type `nice` or `naughty`!")
        """
        member = await self.bot.mongo.fetch_member_info(ctx.author)

        if box_type == "nice" and member.christmas_boxes_nice < amt:
            return await ctx.send("You don't have enough nice boxes to do that!")
        if box_type == "naughty" and member.christmas_boxes_naughty < amt:
            return await ctx.send("You don't have enough naughty boxes to do that!")

        await self.bot.mongo.update_member(
            ctx.author,
            {"$inc": {f"christmas_boxes_{box_type}": -amt, f"christmas_boxes_{box_type}_opened": amt}},
        )
        """
        # Go

        if box_type == "nice":
            rewards = random.choices(*NICE, k=amt)
        else:
            rewards = random.choices(*NAUGHTY, k=amt)

        embed = discord.Embed(
            title=f"Opening {amt} 🎁 {box_type.title()} Box{'es' if amt > 1 else ''}...",
            color=random.choice([0x9ECFFC, 0xDE2E43, 0x79B15A])
        )
        
        update = {
            "$inc": {"premium_balance": 0, "balance": 0, "redeems": 0},
        }
        
        text = []
        added_pokemon = []
        for reward in rewards:
            if reward == "shards":
                shards = max(round(random.normalvariate(25, 10)), 2)
                update["$inc"]["premium_balance"] += shards
                text.append(f"{shards} Shards")

            elif reward == "pokecoins":
                pokecoins = max(round(random.normalvariate(1000, 500)), 800)
                update["$inc"]["balance"] += pokecoins
                text.append(f"{pokecoins} Pokécoins")

            elif reward == "redeem":
                update["$inc"]["redeems"] += 1
                text.append("1 redeem")

            elif reward in ("event", "pokemon", "rare", "shiny"):
                pool = ["Ralts", "Ralts but rarer", "Bowtie Ralts"]
                species = random.choices(pool, weights=[50, 40, 10], k=1)[0]
                level = min(max(int(random.normalvariate(30, 10)), 1), 100)
                shiny = reward == "shiny"
                ivs = [random.randint(0, 31) for i in range(6)]

                pokemon = f"{'✨ ' if shiny else ''}Level {level} {species} ({sum(ivs) / 186:.2%} IV)"
                text.append(pokemon)
                
                added_pokemon.append(pokemon)

            else:
                text.append("Nothing")

        embed.add_field(name="Rewards Received", value="\n".join(text))
        embed.set_author(icon_url=ctx.author.display_avatar.url, name=str(ctx.author))
        """
        await self.bot.mongo.update_member(ctx.author, update)
        if len(added_pokemon) > 0:
            await self.bot.mongo.db.pokemon.insert_many(added_pokemon)
        """
        await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(Test(bot))