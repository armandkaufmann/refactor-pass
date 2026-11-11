export function Column(): PropertyDecorator
/**
 * A column, typed.
 */
export function Column(
    type: string,
    options?: ColumnOptions,
): PropertyDecorator
export function Column(
    typeOrOptions?: string | ColumnOptions,
    options?: ColumnOptions,
): PropertyDecorator {
    return function (object: Object, propertyName: string) {
        register(object, propertyName)
    }
}

export abstract class AbstractLogger {
    protected abstract writeLog(
        level: string,
        message: string,
    ): void

    @Decorated()
    protected abstract other(a: string): Promise<void>

    log(level: string, message: string) {
        this.writeLog(level, message)
    }

    save<Entity>(entity: Entity): Promise<Entity>
    save<Entity>(entities: Entity[]): Promise<Entity[]>
    save<Entity>(entityOrEntities: Entity | Entity[]): Promise<unknown> {
        return Promise.resolve(entityOrEntities)
    }
}

describe("schema", () => {
    let dataSources: DataSource[]
    const defineSuite = (name: string) => {
        it(name, () => {
            check(dataSources)
        })
    }
})

interface Events {
    BeforeQuery: (
        query: string,
    ) => void
    AfterQuery: () => void
}

type Spinner = {
    update: (text: string) => void
}

class Brackets {
    whereFactory: (qb: Builder) => any
    constructor(whereFactory: (qb: Builder) => any) {
        this.whereFactory = whereFactory
    }
}

const handlers = {
    onError: (e: Error) => log(e),
    nested: {
        onClose: () => {
            done()
        },
    },
}

const renderMermaid = useCallback(
    async (definition: string): Promise<boolean> => {
        return true
    },
    [],
)
