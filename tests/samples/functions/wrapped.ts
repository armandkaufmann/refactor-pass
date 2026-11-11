export class OrderService {
  constructor(
    private readonly repo: Repository<Order>,
    @Inject(CONFIG) private readonly config: Config,
  ) {
    this.ready = true;
  }

  async findAll(
    filter: Filter = defaultFilter(),
    @Query('page') page: number = Math.max(1, (base + 1) * 2),
  ): Promise<Order[]> {
    return this.repo.find(filter, page);
  }

  map<
    TInput extends Record<string, unknown>,
    TOutput = TInput,
  >(input: TInput): TOutput {
    return input as unknown as TOutput;
  }

  async load(id: string): Promise<
    Map<string, Array<{ id: string; total: number }>>
  > {
    return new Map();
  }

  @Get(':id')
  @UseGuards(AuthGuard('jwt'))
  findOne(@Param('id') id: string): Order {
    return this.repo.get(id);
  }
}

export function compose<A, B, C>(
  f: (b: B) => C,
  g: (a: A) => B,
): (a: A) => C {
  return (a) => f(g(a));
}
